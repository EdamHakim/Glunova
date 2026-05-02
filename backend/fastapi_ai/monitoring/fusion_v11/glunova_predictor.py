"""Glunova Predictor v11 - production module
Auto-generated from notebook v11. Self-contained Python module.

USAGE
-----
    from glunova_predictor import GlunovaSystem

    system = GlunovaSystem(config_path='glunova_config.json')
    result = system.predict(
        patient_data={
            'age': 52, 'bmi': 30.5,
            'HbA1c_level': 7.2, 'blood_glucose_level': 165,
            'hypertension': 1, 'heart_disease': 0,
            'gender_enc': 0, 'smoking_enc': 2,
        },
        fundus_image_path='/path/to/eye.jpg',
        foot_image_path=None, thermal_image_path=None,
        tongue_image_path=None, cataract_image_path=None,
    )
    print(result['tier'], result['p_finale'], result['recommendation'])
"""
import os, json, joblib, cv2
import numpy as np
import pandas as pd
import torch, torch.nn as nn
import timm
from PIL import Image
from torchvision import transforms, models
import segmentation_models_pytorch as smp
from torch.cuda.amp import autocast


# === MODELE 1 : TABULAR ===
# Sources :
#   - Notebook training : Glunova_Tabular_v8_LateFusion (1).ipynb
#   - Test AUC = 0.9974 | F1 = 0.9784 | overfit gap = 0.64% (excellent)
#   - 33,715 patients test, BorderlineSMOTE-1 50/50, Optuna 30 trials
#
# FIX v11 : validation explicite des champs cliniques obligatoires.
# Avant : un patient_data sans HbA1c -> fallback silencieux a 0 -> faux negatif.
class TabularPredictor:
    # Champs sans lesquels la prediction est cliniquement absurde
    REQUIRED_FIELDS = ['age', 'HbA1c_level', 'blood_glucose_level']

    def __init__(self, model_path, features_path):
        self.model = joblib.load(model_path)
        with open(features_path) as f:
            self.feature_cols = json.load(f)
        print(f" Tabular LightGBM — {len(self.feature_cols)} features")

    def predict(self, patient_data):
        # Validation : champs cliniques obligatoires (FIX v11)
        missing = [f for f in self.REQUIRED_FIELDS if f not in patient_data]
        if missing:
            raise ValueError(
                f"Champs cliniques obligatoires manquants : {missing}. "
                f"HbA1c et glycemie sont indispensables (criteres ADA 2024)."
            )
        df = pd.DataFrame({col: [patient_data.get(col, 0)] for col in self.feature_cols})
        return float(self.model.predict_proba(df)[0][1])


# === MODELE 2 : DR V5.1 BINARY ===
# Sources :
#   - Notebook training : Binary_DR_Phase1_v5_1_COLAB (1).ipynb
#   - Internal AUC = 0.9827 | F1 = 0.9478 | DR-Recall = 0.934
#   - External AUC : IDRiD = 0.9907 | APTOS = 0.9963
#   - Architecture : EfficientNetV2-S, Focal Loss, circular masking, 512x512
#   - Threshold Youden = 0.511 (Sens=0.924, Spec=0.965)
#
# Note v11 : self.threshold est le seuil Youden optimal pour la decision binaire.
# Pour la fusion, on retourne la probabilite continue (probs[1]). Le threshold
# est utilise uniquement par la cascade (cellule 21) pour decider d'appeler V8.
class DRBinaryPredictor:
    def __init__(self, model_path, device='cuda'):
        self.device = device
        self.model = timm.create_model(
            'tf_efficientnetv2_s.in21k_ft_in1k', pretrained=False, num_classes=2,
            drop_rate=0.4, drop_path_rate=0.3,
        )
        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        if 'model_state_dict' in ckpt:
            self.model.load_state_dict(ckpt['model_state_dict'])
        else:
            self.model.load_state_dict(ckpt)
        self.model.to(device).eval()
        self.transform = transforms.Compose([
            transforms.Resize((512, 512)), transforms.ToTensor(),
            transforms.Normalize([0.485,0.456,0.406], [0.229,0.224,0.225]),
        ])
        self.threshold = 0.511  # Youden's J optimal (Sens=0.924, Spec=0.965)
        print(f" DR V5.1 binary — threshold Youden = {self.threshold}")

    def predict(self, image_path):
        """Retourne P(DR) continue. Le seuillage binaire (vs threshold)
        est laisse aux callers (ex: cascade -> V8)."""
        img = Image.open(image_path).convert('RGB')
        x = self.transform(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)[0].cpu().numpy()
        return float(probs[1])


# === MODELE 3 : DR V8 SEVERITY ===
class CFG_V8:
    model_name='convnext_base.fb_in22k_ft_in1k_384'
    num_classes=4; img_size=728; in_chans=4; drop_rate=0.3; drop_path=0.3

def preprocess_image_v8(path, size=CFG_V8.img_size):
    img = cv2.imread(str(path))
    if img is None: return np.zeros((size, size, 3), dtype=np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, th = cv2.threshold(blur, 15, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        (cx,cy), r = cv2.minEnclosingCircle(c)
        cx, cy, r = int(cx), int(cy), int(r)
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask, (cx,cy), int(r*0.97), 255, -1)
        img = cv2.bitwise_and(img, img, mask=mask)
        x1, y1 = max(0,cx-r), max(0,cy-r)
        x2, y2 = min(img.shape[1],cx+r), min(img.shape[0],cy+r)
        img = img[y1:y2, x1:x2]
    h, w = img.shape[:2]
    if h == 0 or w == 0: return np.zeros((size, size, 3), dtype=np.uint8)
    s = size/max(h,w); nh,nw = int(h*s), int(w*s)
    img = cv2.resize(img, (nw,nh), interpolation=cv2.INTER_AREA)
    ph, pw = size-nh, size-nw; t,l = ph//2, pw//2
    img = cv2.copyMakeBorder(img, t,ph-t, l,pw-l, cv2.BORDER_CONSTANT, value=[0,0,0])
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

def extract_green_enhanced_v8(img_rgb):
    g = img_rgb[:,:,1].astype(np.float32)
    b = cv2.GaussianBlur(g, (0,0), sigmaX=CFG_V8.img_size//30)
    e = cv2.addWeighted(g, 4.0, b, -4.0, 128.0)
    return np.clip(e, 0, 255).astype(np.uint8)

def norm4ch_v8(img, ge):
    M=[0.485,0.456,0.406]; S=[0.229,0.224,0.225]; GM,GS=0.500,0.250
    f = img.astype(np.float32)/255.0
    for c in range(3): f[:,:,c] = (f[:,:,c]-M[c])/S[c]
    gf = ge.astype(np.float32)/255.0; gf = (gf-GM)/GS
    return torch.from_numpy(np.dstack([f, gf])).permute(2,0,1).float()

class TriplePoolModel(nn.Module):
    def __init__(self, backbone, num_features=1024, num_classes=4):
        super().__init__()
        self.backbone = backbone
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.quad_pool = nn.AdaptiveAvgPool2d(2)
        total = num_features*6
        self.drop = nn.Dropout(CFG_V8.drop_rate)
        self.head = nn.Linear(total, num_classes)
    def forward(self, x):
        f = self.backbone.forward_features(x)
        avg = self.avg_pool(f).flatten(1)
        mx = self.max_pool(f).flatten(1)
        quad = self.quad_pool(f).flatten(1)
        return self.head(self.drop(torch.cat([avg,mx,quad], dim=1)))

def tta_pred_v8(model, t):
    tfs = [
        lambda x: x, lambda x: torch.flip(x,[3]), lambda x: torch.flip(x,[2]),
        lambda x: torch.flip(x,[2,3]), lambda x: torch.rot90(x,1,[2,3]),
        lambda x: torch.rot90(x,2,[2,3]), lambda x: torch.rot90(x,3,[2,3]),
        lambda x: torch.flip(torch.rot90(x,1,[2,3]), [3]),
    ]
    with torch.no_grad():
        with autocast():
            ps = [torch.softmax(model(f(t)), 1) for f in tfs]
    return torch.stack(ps).mean(0)

class DRSeverityPredictor:
    GRADE_NAMES = ['Mild','Moderate','Severe','Proliferative']
    def __init__(self, model_path, device='cuda'):
        self.device = device
        backbone = timm.create_model(CFG_V8.model_name, pretrained=False, num_classes=0,
            in_chans=CFG_V8.in_chans, drop_rate=0.0, drop_path_rate=CFG_V8.drop_path)
        self.model = TriplePoolModel(backbone, 1024, 4)
        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        if isinstance(ckpt, dict) and 'model_state_dict' in ckpt:
            self.model.load_state_dict(ckpt['model_state_dict'])
        else:
            self.model.load_state_dict(ckpt)
        self.model.to(device).eval()
        print(" DR V8 severity — ConvNeXt + TriplePool + TTA")

    def predict(self, image_path):
        img = preprocess_image_v8(image_path)
        ge = extract_green_enhanced_v8(img)
        x = norm4ch_v8(img, ge).unsqueeze(0).to(self.device)
        probs = tta_pred_v8(self.model, x)[0].cpu().numpy()
        idx = int(probs.argmax())
        return {'grade': idx+1, 'grade_name': self.GRADE_NAMES[idx],
                'probs': probs, 'confidence': float(probs.max())}


# === MODELE 4 : THERMAL FOOT ===
class ThermalFootPredictor:
    def __init__(self, model_path, device='cuda'):
        self.device = device
        self.model = timm.create_model('resnet50', pretrained=False, num_classes=2)
        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        if isinstance(ckpt, dict) and 'state_dict' in ckpt:
            self.model.load_state_dict(ckpt['state_dict'])
        else:
            self.model.load_state_dict(ckpt)
        self.model.to(device).eval()
        self.transform = transforms.Compose([
            transforms.Resize((224,224)), transforms.ToTensor(),
            transforms.Normalize([0.485,0.456,0.406], [0.229,0.224,0.225]),
        ])
        print(" ThermalFoot — ResNet50 224px")

    def predict(self, image_path):
        img = Image.open(image_path).convert('RGB')
        x = self.transform(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)[0].cpu().numpy()
        return float(probs[0])  # P(DF)


# === MODELE 5 : DFU UNET ===
class DFUSegmentationPredictor:
    def __init__(self, model_path, device='cuda'):
        self.device = device
        self.model = smp.Unet(encoder_name="resnet34", encoder_weights=None,
                              in_channels=3, classes=1, activation=None)
        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        if isinstance(ckpt, dict) and 'state_dict' in ckpt:
            self.model.load_state_dict(ckpt['state_dict'])
        else:
            self.model.load_state_dict(ckpt)
        self.model.to(device).eval()
        self.transform = transforms.Compose([
            transforms.Resize((512,512)), transforms.ToTensor(),
            transforms.Normalize([0.485,0.456,0.406], [0.229,0.224,0.225]),
        ])
        self.threshold = 0.5
        print(" DFU UNet — Dice 0.8706")

    def predict(self, image_path, use_tta=True):
        img = Image.open(image_path).convert('RGB')
        x = self.transform(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            if use_tta:
                l1 = self.model(x)
                l2 = torch.flip(self.model(torch.flip(x,[3])), [3])
                l3 = torch.flip(self.model(torch.flip(x,[2])), [2])
                logits = (l1+l2+l3)/3.0
            else:
                logits = self.model(x)
            probs_map = torch.sigmoid(logits)[0,0].cpu().numpy()
        mask = (probs_map >= self.threshold).astype(np.uint8)
        ratio = float(mask.sum()/mask.size)
        max_p = float(probs_map.max())
        if ratio >= 0.001:
            score = min(0.5 + ratio*20 + max_p*0.2, 1.0)
        elif max_p >= 0.5:
            score = 0.3 + max_p*0.3
        else:
            score = max_p*0.4
        return float(score)


# === MODELE 6 : TONGUE ===
class TonguePredictor:
    """Wrapper du Tongue ResNet50.

    Architecture confirmee par inspection du checkpoint :
    - Backbone : ResNet50 (torchvision)
    - Classifier : nn.Sequential(Dropout, Linear(2048, 1))
    - Output : 1 logit -> sigmoid -> P(diabete)
    - Binary classification avec BCE loss
    """

    def __init__(self, model_path, device='cuda'):
        self.device = device

        self.model = models.resnet50(weights=None)
        in_f = self.model.fc.in_features  # 2048

        self.model.fc = nn.Sequential(
            nn.Dropout(p=0.5),
            nn.Linear(in_f, 1),
        )

        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        if isinstance(ckpt, dict):
            if 'state_dict' in ckpt:
                state_dict = ckpt['state_dict']
            elif 'model_state_dict' in ckpt:
                state_dict = ckpt['model_state_dict']
            else:
                state_dict = ckpt
        else:
            state_dict = ckpt

        try:
            self.model.load_state_dict(state_dict, strict=True)
            self.arch_used = 'resnet50_dropout_linear1'
            print(f"[OK] Tongue loaded — ResNet50 + Dropout + Linear(2048, 1)")
        except Exception as e:
            print(f"[WARN] Strict loading failed: {str(e)[:100]}")
            print(f"[INFO] Trying alternative architectures...")

            try:
                self.model = models.resnet50(weights=None)
                self.model.fc = nn.Sequential(
                    nn.Identity(),
                    nn.Linear(in_f, 1),
                )
                self.model.load_state_dict(state_dict, strict=True)
                self.arch_used = 'resnet50_identity_linear1'
                print(f" Tongue loaded — Identity + Linear(2048, 1)")
            except Exception:
                try:
                    self.model = models.resnet50(weights=None)
                    self.model.fc = nn.Sequential(
                        nn.Flatten(),
                        nn.Linear(in_f, 1),
                    )
                    self.model.load_state_dict(state_dict, strict=True)
                    self.arch_used = 'resnet50_flatten_linear1'
                    print(f"[OK] Tongue loaded — Flatten + Linear(2048, 1)")
                except Exception:
                    print(f"[WARN] All strict attempts failed, using non-strict")
                    self.model = models.resnet50(weights=None)
                    self.model.fc = nn.Sequential(
                        nn.Dropout(p=0.5),
                        nn.Linear(in_f, 1),
                    )
                    msg = self.model.load_state_dict(state_dict, strict=False)
                    self.arch_used = 'resnet50_nonstrict'
                    print(f"  Missing : {len(msg.missing_keys)}")
                    print(f"  Unexpected : {len(msg.unexpected_keys)}")

        self.model.to(device).eval()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        print(f"     Architecture : {self.arch_used}")
        print(f"     Output       : 1 logit -> sigmoid -> P(diabete)")

    def predict(self, image_path):
        """Predict P(diabetes) from tongue image."""
        img = Image.open(image_path).convert('RGB')
        x = self.transform(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logit = self.model(x)
            p_diabetes = torch.sigmoid(logit).squeeze().cpu().item()
        return float(p_diabetes)


# === MODELE 7 : CATARACT (MobileNetV3-Large, 4-class) ===
class CataractPredictor:
    """Wrapper du modele Cataract de Ghofrane.

    Architecture (verifiee par inspection du checkpoint et de build_model('mobilenet')) :
    - Backbone : MobileNetV3-Large (torchvision)
    - Classifier : Sequential(
          Linear(960, 256), Hardswish(),
          Dropout(0.3), Linear(256, 4)
      )
    - Output : 4 logits -> softmax -> [normale, legere, moderee, severe]

    On expose :
    - predict(path) -> dict avec :
        * grade        : int 0..3 (0=normale)
        * grade_name   : str
        * confidence   : float (max softmax)
        * probs        : list de 4 floats
        * p_cataract   : float = P(toute cataracte) = 1 - P(normale)
                         C'est cette valeur qui rentre dans la fusion.
    """

    CLASS_NAMES = ['normale', 'legere', 'moderee', 'severe']
    IMG_SIZE    = 224
    MEAN        = [0.485, 0.456, 0.406]
    STD         = [0.229, 0.224, 0.225]

    def __init__(self, model_path, device='cuda'):
        self.device = device

        # Architecture exacte issue du build_model('mobilenet') de Ghofrane
        self.model = models.mobilenet_v3_large(weights=None)
        n = self.model.classifier[0].in_features  # 960

        self.model.classifier = nn.Sequential(
            nn.Linear(n, 256),
            nn.Hardswish(),
            nn.Dropout(0.3),
            nn.Linear(256, 4),
        )

        # Charger le checkpoint (Ghofrane sauvegarde un dict)
        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        if isinstance(ckpt, dict):
            if 'model_state_dict' in ckpt:
                state_dict = ckpt['model_state_dict']
            elif 'state_dict' in ckpt:
                state_dict = ckpt['state_dict']
            else:
                state_dict = ckpt
        else:
            state_dict = ckpt

        try:
            self.model.load_state_dict(state_dict, strict=True)
            self.arch_used = 'mobilenetv3_large_strict'
            print(f"[OK] Cataract loaded — MobileNetV3-Large (strict)")
        except Exception as e:
            print(f"[WARN] Strict loading failed: {str(e)[:120]}")
            print(f"[INFO] Retrying with strict=False")
            msg = self.model.load_state_dict(state_dict, strict=False)
            self.arch_used = 'mobilenetv3_large_nonstrict'
            print(f"  Missing keys    : {len(msg.missing_keys)}")
            print(f"  Unexpected keys : {len(msg.unexpected_keys)}")

        self.model.to(device).eval()

        self.transform = transforms.Compose([
            transforms.Resize((self.IMG_SIZE, self.IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(self.MEAN, self.STD),
        ])

        # Afficher les metadonnees du checkpoint si presentes
        if isinstance(ckpt, dict):
            for key in ['test_accuracy', 'test_f1_macro', 'test_auc_macro']:
                if key in ckpt:
                    print(f"     {key:18s} : {ckpt[key]}")

        print(f"     Architecture : {self.arch_used}")
        print(f"     Classes      : {self.CLASS_NAMES}")

    def predict(self, image_path):
        """Predict cataract grade.

        Returns:
            dict {grade, grade_name, confidence, probs, p_cataract}
        """
        img = Image.open(image_path).convert('RGB')
        x = self.transform(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)[0].cpu().numpy()

        grade = int(probs.argmax())
        return {
            'grade'      : grade,
            'grade_name' : self.CLASS_NAMES[grade],
            'confidence' : float(probs[grade]),
            'probs'      : probs.tolist(),
            # P(toute cataracte) = somme des classes >= 1
            'p_cataract' : float(probs[1] + probs[2] + probs[3]),
        }


# === Confidence factor recalibre pour 7 modeles ===
# La courbe est concave (chaque modele manquant fait plus mal que le precedent)
# Calibree pour preserver la coherence avec les 4 patients de v10.1
CONFIDENCE_FACTORS = {
    7: 1.00,   # Tous presents — confiance maximale
    6: 0.97,   # 1 manquant — perte minimale
    5: 0.92,   # 2 manquants — encore solide
    4: 0.83,   # 3 manquants — confiance modeste
    3: 0.73,   # 4 manquants — incertain
    2: 0.62,   # Tabular + 1 image — verdict prudent
    1: 0.50,   # Tabular seul — quick check, jamais CRITICAL
    0: 0.00,   # Pas de Tabular = erreur (Tabular obligatoire)
}

# Seuils override DR V8 (inchange v10.1)
OVERRIDE_CONFIDENCE_THRESHOLD = 0.75

# Seuil asymetrie clinique pour Thermal / DFU / Cataract
COMPLICATION_THRESHOLD = 0.30

# === SEUILS DE TIER (3 TIERS, inchange v10.1) ===
TIER_CRITICAL_THRESHOLD = 0.90
TIER_HIGH_THRESHOLD = 0.45

# Seuils co-occurrence
TABULAR_HIGH_THRESHOLD = 0.80
DR_DETECTED_THRESHOLD = 0.50

# Tier hierarchy pour comparaison
TIER_RANK = {'LOW': 0, 'HIGH': 1, 'CRITICAL': 2}
RANK_TO_TIER = {0: 'LOW', 1: 'HIGH', 2: 'CRITICAL'}


def late_fusion_robust(features_dict, dr_grade=0, dr_grade_confidence=0.0,
                       cataract_grade=0, cataract_confidence=0.0):
    """Late Fusion robuste v11 - 3 tiers (LOW / HIGH / CRITICAL), 7 modeles.

    Changements vs v10.1 :
    - Ajout du signal cataract (asymetrie clinique)
    - Confidence factors recalibres sur 7 niveaux
    - Args cataract_grade / cataract_confidence remontes pour future utilisation

    Args:
        features_dict : scores des modeles (None si absent)
            Cles attendues : p_tabular, p_dr_v51, p_thermal, p_ulcer, p_tongue, p_cataract
        dr_grade : 0-4 (0=No DR, 4=Proliferative)
        dr_grade_confidence : 0-1
        cataract_grade : 0-3 (0=normale, 3=severe) — non utilise en v11
                         (place pour override clinique futur)
        cataract_confidence : 0-1 — non utilise en v11

    Returns:
        dict avec p_finale, tier, contributions, etc.
    """
    # === ETAPE 1 : Tabular obligatoire ===
    available_raw = {k: v for k, v in features_dict.items() if v is not None}

    if 'p_tabular' not in available_raw:
        return {
            'error': 'TABULAR_REQUIRED',
            'message': 'Donnees cliniques (HbA1c, glucose) obligatoires.',
            'tier': None,
        }

    # === ETAPE 2 : ASYMETRIE CLINIQUE - Filtrer Thermal / DFU / Cataract bas ===
    available = dict(available_raw)
    asymmetry_filtered = []

    if 'p_thermal' in available and available['p_thermal'] < COMPLICATION_THRESHOLD:
        asymmetry_filtered.append(
            f'p_thermal ({available["p_thermal"]:.3f}) < {COMPLICATION_THRESHOLD}'
        )
        del available['p_thermal']

    if 'p_ulcer' in available and available['p_ulcer'] < COMPLICATION_THRESHOLD:
        asymmetry_filtered.append(
            f'p_ulcer ({available["p_ulcer"]:.3f}) < {COMPLICATION_THRESHOLD}'
        )
        del available['p_ulcer']

    # NEW v11 : Cataract asymetrique (presence informe, absence neutre)
    if 'p_cataract' in available and available['p_cataract'] < COMPLICATION_THRESHOLD:
        asymmetry_filtered.append(
            f'p_cataract ({available["p_cataract"]:.3f}) < {COMPLICATION_THRESHOLD}'
        )
        del available['p_cataract']

    # === ETAPE 3 : Renormalisation ===
    available_weights = {k: CLINICAL_WEIGHTS[k] for k in available}
    total_w = sum(available_weights.values())
    norm_weights = {k: w/total_w for k, w in available_weights.items()}

    # === ETAPE 4 : Calculer P_finale ===
    p_finale = sum(norm_weights[k] * available[k] for k in available)
    contributions = {k: norm_weights[k] * available[k] for k in available}

    # === ETAPE 5 : Confidence factor (sur n_models_raw, AVANT filtrage asymetrie) ===
    n_models_raw = len(available_raw)
    confidence_factor = CONFIDENCE_FACTORS.get(n_models_raw, 0.5)

    # === ETAPE 6 : Override CRITICAL (Severe / Proliferative) ===
    override_active = False
    override_reason = None

    if dr_grade == 4 and dr_grade_confidence >= OVERRIDE_CONFIDENCE_THRESHOLD:
        override_active = True
        override_reason = f'Proliferative DR avec confidence {dr_grade_confidence:.2f}'
        return {
            'p_finale': p_finale,
            'tier': 'CRITICAL',
            'reasons': ['Proliferative DR detected — vision menacee'],
            'recommendation': 'Consultation ophtalmologique URGENTE',
            'contributions': contributions,
            'norm_weights': norm_weights,
            'confidence_factor': confidence_factor,
            'n_models_used': n_models_raw,
            'override_active': override_active,
            'override_reason': override_reason,
            'asymmetry_filtered': asymmetry_filtered,
        }

    if dr_grade == 3 and dr_grade_confidence >= OVERRIDE_CONFIDENCE_THRESHOLD:
        override_active = True
        override_reason = f'Severe DR avec confidence {dr_grade_confidence:.2f}'
        return {
            'p_finale': p_finale,
            'tier': 'CRITICAL',
            'reasons': ['Severe DR detected'],
            'recommendation': 'Consultation ophtalmologique sous 1 mois',
            'contributions': contributions,
            'norm_weights': norm_weights,
            'confidence_factor': confidence_factor,
            'n_models_used': n_models_raw,
            'override_active': override_active,
            'override_reason': override_reason,
            'asymmetry_filtered': asymmetry_filtered,
        }

    # === ETAPE 7 : Tier de base sur P_finale (3 TIERS) ===
    reasons = []

    if p_finale >= TIER_CRITICAL_THRESHOLD:
        base_tier = 'CRITICAL'
        reasons.append(f'P(diabete)={p_finale:.2f} - tres eleve')
    elif p_finale >= TIER_HIGH_THRESHOLD:
        base_tier = 'HIGH'
        reasons.append(f'P(diabete)={p_finale:.2f}')
    else:
        base_tier = 'LOW'
        reasons.append(f'P(diabete)={p_finale:.2f}')

    final_tier = base_tier
    boost_reasons = []

    # === ETAPE 8 : BOOST 1 - Override Grade=2 (vers HIGH) ===
    if dr_grade == 2 and dr_grade_confidence >= OVERRIDE_CONFIDENCE_THRESHOLD:
        if TIER_RANK[final_tier] < TIER_RANK['HIGH']:
            final_tier = 'HIGH'
            boost_reasons.append(
                f'Boost LOW->HIGH : Moderate DR confirme par V8 (confidence {dr_grade_confidence:.2f})'
            )

    # === ETAPE 9 : BOOST 2 - Co-occurrence Tabular + DR V5.1 (vers HIGH) ===
    p_tab = available_raw.get('p_tabular', 0)
    p_dr = available_raw.get('p_dr_v51', 0)

    if p_tab >= TABULAR_HIGH_THRESHOLD and p_dr >= DR_DETECTED_THRESHOLD:
        if TIER_RANK[final_tier] < TIER_RANK['HIGH']:
            final_tier = 'HIGH'
            boost_reasons.append(
                f'Boost vers HIGH : Tabular={p_tab:.2f} + DR V5.1={p_dr:.2f} '
                f'(2 marqueurs majeurs concordants)'
            )

    # === ETAPE 10 : BOOST 3 - Tabular + DR Grade>=2 (vers HIGH) ===
    if p_tab >= TABULAR_HIGH_THRESHOLD and dr_grade >= 2:
        if TIER_RANK[final_tier] < TIER_RANK['HIGH']:
            final_tier = 'HIGH'
            boost_reasons.append(
                f'Boost vers HIGH : Tabular={p_tab:.2f} + DR Grade={dr_grade} '
                f'(diabete + complication oculaire)'
            )

    # === ETAPE 11 : CAP CLINIQUE - jamais CRITICAL avec 1 seul modele ===
    # Justification clinique :
    #  - 1 seul modele actif = confidence factor 50% (~pile-ou-face) -> incompatible
    #    avec une recommandation "consultation immediate" (CRITICAL).
    #  - ADA 2024 Section 2 (Diagnosis) : un diagnostic de diabete necessite
    #    "a second test for confirmation" sauf urgence clinique evidente.
    #  - HbA1c isolee peut etre faussement elevee (anemie ferriprive, IRC, transfusion)
    #    ou faussement basse (hemolyse, hemoglobinopathie, saignement) -> Cohen 2003.
    #  - Asymetrie cout : faux-positif CRITICAL (urgence inutile + anxiete + cout)
    #    >> faux-positif HIGH (consultation specialiste sous 3-6 mois).
    #  - Coherence design : la valeur ajoutee de Glunova = multimodalite ;
    #    sans 2+ signaux concordants, on plafonne explicitement.
    if n_models_raw == 1 and final_tier == 'CRITICAL':
        boost_reasons.append(
            'Cap clinique : 1 seul modele actif -> tier maximum HIGH. '
            'Consultation immediate necessite >= 2 signaux concordants '
            '(ADA 2024 confirmation rule + multimodalite Glunova).'
        )
        final_tier = 'HIGH'

    # === ETAPE 12 : Avertissements ===
    if dr_grade >= 3 and dr_grade_confidence < OVERRIDE_CONFIDENCE_THRESHOLD:
        reasons.append(
            f'V8 a predit grade {dr_grade} mais confidence basse ({dr_grade_confidence:.2f}) '
            f'-- override non declenche, examen ophtalmologique recommande'
        )

    if 'p_dr_v51' not in available_raw:
        reasons.append('Examen ophtalmologique (fundus) recommande')

    if 'p_ulcer' not in available_raw and 'p_thermal' not in available_raw:
        reasons.append('Examen pied (DFU + thermal) recommande')

    if 'p_cataract' not in available_raw:
        reasons.append('Examen cataracte (slit-lamp ou fundus) recommande')

    reasons.extend(boost_reasons)

    if asymmetry_filtered:
        for f in asymmetry_filtered:
            reasons.append(f'Asymetrie clinique : {f} (traite comme absent)')

    # === RECOMMANDATIONS 3 TIERS ===
    recommendations = {
        'LOW':      'Suivi annuel standard',
        'HIGH':     'Suivi 3-6 mois + specialiste',
        'CRITICAL': 'Consultation immediate',
    }

    return {
        'p_finale': p_finale,
        'tier': final_tier,
        'reasons': reasons,
        'recommendation': recommendations[final_tier],
        'contributions': contributions,
        'norm_weights': norm_weights,
        'confidence_factor': confidence_factor,
        'n_models_used': n_models_raw,
        'override_active': override_active,
        'override_reason': override_reason,
        'asymmetry_filtered': asymmetry_filtered,
    }


# ============================================================================
# GlunovaSystem - Production entry point
# ============================================================================
class GlunovaSystem:
    """Production-ready Glunova v11 predictor.

    Charge les 7 modeles ML une seule fois (init), expose .predict() pour les
    requetes HTTP. Utilise par le backend FastAPI.
    """

    def __init__(self, config_path=None, config_dict=None, device=None):
        if config_path:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        elif config_dict:
            self.config = config_dict
        else:
            raise ValueError('Provide config_path or config_dict')

        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        # Override des constantes globales avec celles du config
        global CLINICAL_WEIGHTS, CONFIDENCE_FACTORS
        if 'clinical_weights' in self.config:
            CLINICAL_WEIGHTS = self.config['clinical_weights']
        if 'confidence_factors' in self.config:
            CONFIDENCE_FACTORS = {int(k): v for k, v in self.config['confidence_factors'].items()}

        paths = self.config['model_paths']
        print(f'[GlunovaSystem] Loading 7 models on {self.device}...')
        self.tabular  = TabularPredictor(paths['tabular_model'], paths['tabular_features'])
        self.dr_v51   = DRBinaryPredictor(paths['dr_v51'], device=self.device)
        self.dr_v8    = DRSeverityPredictor(paths['dr_v8'], device=self.device)
        self.thermal  = ThermalFootPredictor(paths['thermal'], device=self.device)
        self.dfu      = DFUSegmentationPredictor(paths['dfu'], device=self.device)
        self.tongue   = TonguePredictor(paths['tongue'], device=self.device)
        self.cataract = CataractPredictor(paths['cataract'], device=self.device)
        print(f'[GlunovaSystem] Ready (v{self.config.get("version", "11")})')

    def predict(self, patient_data,
                fundus_image_path=None, foot_image_path=None,
                thermal_image_path=None, tongue_image_path=None,
                cataract_image_path=None):
        # 1. Tabular (REQUIRED)
        p_tabular = self.tabular.predict(patient_data)

        # 2-3. DR cascade
        p_dr_v51 = None
        dr_grade = 0
        dr_confidence = 0.0
        if fundus_image_path and os.path.exists(fundus_image_path):
            p_dr_v51 = self.dr_v51.predict(fundus_image_path)
            if p_dr_v51 >= self.dr_v51.threshold:
                v8 = self.dr_v8.predict(fundus_image_path)
                dr_grade = v8['grade']
                dr_confidence = v8['confidence']

        # 4-7. Other modalities (all optional)
        p_thermal = self.thermal.predict(thermal_image_path) if (thermal_image_path and os.path.exists(thermal_image_path)) else None
        p_ulcer   = self.dfu.predict(foot_image_path, use_tta=True) if (foot_image_path and os.path.exists(foot_image_path)) else None
        p_tongue  = self.tongue.predict(tongue_image_path) if (tongue_image_path and os.path.exists(tongue_image_path)) else None

        p_cataract = None
        cataract_grade = 0
        cataract_confidence = 0.0
        if cataract_image_path and os.path.exists(cataract_image_path):
            cat = self.cataract.predict(cataract_image_path)
            p_cataract = cat['p_cataract']
            cataract_grade = cat['grade']
            cataract_confidence = cat['confidence']

        features = {
            'p_tabular': p_tabular, 'p_dr_v51': p_dr_v51,
            'p_thermal': p_thermal, 'p_ulcer': p_ulcer,
            'p_tongue': p_tongue, 'p_cataract': p_cataract,
        }
        result = late_fusion_robust(
            features,
            dr_grade=dr_grade, dr_grade_confidence=dr_confidence,
            cataract_grade=cataract_grade, cataract_confidence=cataract_confidence,
        )

        result['features'] = features
        result['dr_grade'] = dr_grade
        result['dr_confidence'] = dr_confidence
        result['cataract_grade'] = cataract_grade
        result['cataract_confidence'] = cataract_confidence
        return result
