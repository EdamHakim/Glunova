from __future__ import annotations

import base64
import io
import sys
import wave
from dataclasses import dataclass
from threading import Lock

import joblib
import librosa
import matplotlib
matplotlib.use("Agg")

import numpy as np
import torch
import torchaudio
from matplotlib.figure import Figure

try:
    import shap
except Exception:  # pragma: no cover - optional runtime dependency
    shap = None

from screening.voice_config import (
    VOICE_BYOLS_CHECKPOINT,
    VOICE_BYOLS_REPO,
    VOICE_MAX_UPLOAD_BYTES,
    VOICE_MIN_DURATION_S,
    VOICE_MIN_MEAN_RMS,
    VOICE_MIN_VOICED_RATIO,
    VOICE_MODEL_NAME,
    VOICE_MODEL_VERSION,
    VOICE_SAMPLE_RATE,
    VOICE_SHAP_SEGMENTS,
    VOICE_SVM_ARTIFACT_PATH,
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class VoiceInferenceResult:
    probability: float
    raw_probability: float
    prediction_index: int
    prediction_label: str
    threshold_used: float
    decision_score: float
    ood_mahal_score: float
    ood_flag: bool
    shap_ready: bool
    shap_message: str
    shap_base_value: float | None
    shap_segments: list[dict]
    shap_plot_base64: str | None
    model_name: str = VOICE_MODEL_NAME
    model_version: str = VOICE_MODEL_VERSION


class VoiceSvmService:
    def __init__(self):
        self.model_path = VOICE_SVM_ARTIFACT_PATH
        self.byols_repo = VOICE_BYOLS_REPO
        self.byols_checkpoint = VOICE_BYOLS_CHECKPOINT
        self.max_upload_bytes = VOICE_MAX_UPLOAD_BYTES
        self._artifact: dict | None = None
        self._byols_model = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        return self._artifact is not None

    def ensure_loaded(self) -> None:
        if self._artifact is not None:
            return
        with self._load_lock:
            if self._artifact is not None:
                return
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Voice model artifact not found at {self.model_path.as_posix()}. "
                    "Copy vocadiab_voice_svm_model.joblib under screening/models/voice/."
                )
            self._artifact = joblib.load(self.model_path)

    def _ensure_byols_model(self):
        if self._byols_model is not None:
            return self._byols_model

        if not self.byols_repo.exists():
            raise FileNotFoundError(
                f"BYOL-S repository not found at {self.byols_repo.as_posix()}. "
                "Set VOICE_BYOLS_REPO or copy serab-byols under screening/models/voice/."
            )
        if not self.byols_checkpoint.exists():
            raise FileNotFoundError(
                f"BYOL-S checkpoint not found at {self.byols_checkpoint.as_posix()}."
            )

        if str(self.byols_repo) not in sys.path:
            sys.path.insert(0, str(self.byols_repo))

        if not hasattr(torchaudio, "set_audio_backend"):
            torchaudio.set_audio_backend = lambda *_args, **_kwargs: None

        import serab_byols  # type: ignore

        model = serab_byols.load_model(str(self.byols_checkpoint), model_name="cvt")
        model = model.to(DEVICE)
        model.eval()
        self._byols_model = (serab_byols, model)
        return self._byols_model

    def assess_audio_quality(self, audio_bytes: bytes) -> dict:
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=VOICE_SAMPLE_RATE, mono=True)
        duration_s = len(y) / sr if sr > 0 else 0.0
        rms = librosa.feature.rms(y=y)[0]
        mean_rms = float(np.mean(rms))

        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        _ = f0
        voiced_ratio = float(np.nanmean(voiced_flag.astype(float))) if voiced_flag is not None else 0.0

        reasons: list[str] = []
        if duration_s < VOICE_MIN_DURATION_S:
            reasons.append(f"audio is too short (minimum {VOICE_MIN_DURATION_S:.1f}s)")
        if mean_rms < VOICE_MIN_MEAN_RMS:
            reasons.append("audio energy is too low (too quiet or mostly silence)")
        if voiced_ratio < VOICE_MIN_VOICED_RATIO:
            reasons.append("voiced speech content is too low")

        return {
            "ok": len(reasons) == 0,
            "duration_s": float(duration_s),
            "mean_rms": mean_rms,
            "voiced_ratio": voiced_ratio,
            "reasons": reasons,
        }

    def _extract_voice_embedding(self, audio_bytes: bytes) -> np.ndarray:
        serab_byols, model = self._ensure_byols_model()
        y, _ = librosa.load(io.BytesIO(audio_bytes), sr=VOICE_SAMPLE_RATE, mono=True)
        audio_batch = torch.from_numpy(y.astype(np.float32)).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            emb = serab_byols.get_scene_embeddings(audio_batch, model)

        emb = emb.squeeze(0).detach().cpu().numpy().astype(np.float32)
        if emb.ndim != 1:
            emb = emb.reshape(-1)
        if emb.shape[0] < 2048:
            emb = np.pad(emb, (0, 2048 - emb.shape[0]))
        elif emb.shape[0] > 2048:
            emb = emb[:2048]
        return emb

    @staticmethod
    def _wav_bytes_from_signal(y: np.ndarray, sr: int) -> bytes:
        buf = io.BytesIO()
        y_clipped = np.clip(y.astype(np.float32), -1.0, 1.0)
        pcm16 = (y_clipped * 32767.0).astype(np.int16)
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(int(sr))
            wav_file.writeframes(pcm16.tobytes())
        return buf.getvalue()

    @staticmethod
    def _build_shap_overlay_base64(y: np.ndarray, sr: int, segments: list[dict]) -> str | None:
        if len(y) == 0 or not segments:
            return None

        t_plot = np.arange(len(y)) / float(sr)
        shap_values = np.array([float(segment["shap_value"]) for segment in segments], dtype=np.float64)
        max_abs = max(1e-8, float(np.max(np.abs(shap_values))))
        norm = matplotlib.colors.Normalize(vmin=-max_abs, vmax=max_abs)
        cmap = matplotlib.colormaps["coolwarm"]

        fig = Figure(figsize=(13, 6), dpi=140)
        axes = fig.subplots(2, 1, sharex=True)

        for segment in segments:
            axes[0].axvspan(
                float(segment["start_s"]),
                float(segment["end_s"]),
                color=cmap(norm(float(segment["shap_value"]))),
                alpha=0.35,
                linewidth=0,
            )
        axes[0].plot(t_plot, y, color="#1F1F1F", linewidth=0.8)
        axes[0].set_title("Waveform With SHAP Segment Overlay")
        axes[0].set_ylabel("Amplitude")

        starts = np.array([float(segment["start_s"]) for segment in segments], dtype=np.float64)
        ends = np.array([float(segment["end_s"]) for segment in segments], dtype=np.float64)
        centers = 0.5 * (starts + ends)
        widths = ends - starts
        bar_colors = [cmap(norm(value)) for value in shap_values]
        axes[1].bar(centers, shap_values, width=widths * 0.95, color=bar_colors, edgecolor="white")
        axes[1].axhline(0.0, color="black", linewidth=1)
        axes[1].set_title("SHAP Value By Time Segment")
        axes[1].set_xlabel("Time (s)")
        axes[1].set_ylabel("SHAP Value")

        sm = matplotlib.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        fig.tight_layout(rect=[0.0, 0.1, 1.0, 1.0])
        cax = fig.add_axes([0.22, 0.04, 0.56, 0.03])
        cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
        cbar.set_label("SHAP value")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _segment_shap_xai(self, artifact: dict, audio_bytes: bytes) -> tuple[bool, str, float | None, list[dict], str | None]:
        if shap is None:
            return False, "SHAP package is not installed.", None, [], None

        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=VOICE_SAMPLE_RATE, mono=True)
        if len(y) == 0:
            return False, "Audio is empty; cannot compute SHAP.", None, [], None

        pipe = artifact["pipeline"]
        n_segments = max(6, min(int(VOICE_SHAP_SEGMENTS), 24))
        edges = np.linspace(0, len(y), n_segments + 1, dtype=int)

        def _predict_from_masks(mask_matrix):
            mask_matrix = np.atleast_2d(mask_matrix).astype(np.float32)
            probs = []
            for mask_row in mask_matrix:
                y_masked = y.copy()
                mask_row = np.clip(mask_row, 0.0, 1.0)
                for i in range(n_segments):
                    s, e = int(edges[i]), int(edges[i + 1])
                    if e <= s:
                        continue
                    y_masked[s:e] *= float(mask_row[i])
                emb = self._extract_voice_embedding(self._wav_bytes_from_signal(y_masked, sr)).reshape(1, -1)
                probs.append(float(pipe.predict_proba(emb)[0, 1]))
            return np.array(probs, dtype=np.float64)

        background = np.vstack([np.zeros((1, n_segments), dtype=np.float32), np.ones((1, n_segments), dtype=np.float32)])
        x_full = np.ones((1, n_segments), dtype=np.float32)

        try:
            explainer = shap.KernelExplainer(_predict_from_masks, background, link="identity")
            shap_values = explainer.shap_values(x_full, nsamples=96)
            if isinstance(shap_values, list):
                shap_vec = np.asarray(shap_values[0], dtype=np.float64).reshape(1, -1)[0]
            else:
                shap_vec = np.asarray(shap_values, dtype=np.float64).reshape(1, -1)[0]
            base_value = float(np.asarray(explainer.expected_value).reshape(-1)[0])
        except Exception as exc:
            return False, f"SHAP computation failed: {exc}", None, [], None

        segments: list[dict] = []
        for i in range(n_segments):
            s, e = int(edges[i]), int(edges[i + 1])
            segments.append(
                {
                    "segment": i + 1,
                    "start_s": float(s / sr),
                    "end_s": float(e / sr),
                    "shap_value": float(shap_vec[i]),
                    "abs_shap": float(abs(shap_vec[i])),
                }
            )
        plot_base64 = self._build_shap_overlay_base64(y, sr, segments)
        return True, "ok", base_value, segments, plot_base64

    def predict(self, audio_bytes: bytes) -> VoiceInferenceResult:
        self.ensure_loaded()
        assert self._artifact is not None
        artifact = self._artifact

        if len(audio_bytes) > self.max_upload_bytes:
            raise ValueError(f"Audio exceeds maximum size ({self.max_upload_bytes} bytes).")
        if not audio_bytes:
            raise ValueError("Uploaded audio is empty.")

        quality = self.assess_audio_quality(audio_bytes)
        if not quality["ok"]:
            raise ValueError("Audio quality is not sufficient: " + "; ".join(quality["reasons"]))

        with self._inference_lock:
            embedding = self._extract_voice_embedding(audio_bytes)
            pipe = artifact["pipeline"]
            sc = pipe.named_steps["sc"]
            pca = pipe.named_steps["pca"]
            clf = pipe.named_steps["clf"]
            x = embedding.reshape(1, -1)
            raw_prob = float(pipe.predict_proba(x)[0, 1])
            x_pc = pca.transform(sc.transform(x))[0]
            baseline_decision = float(clf.decision_function([x_pc])[0])

            pc_mean = artifact["train_pc_mean"]
            pc_std = artifact.get("train_pc_std", np.ones_like(pc_mean))
            z = (x_pc - pc_mean) / (pc_std + 1e-8)
            mahal = float(np.sqrt(np.mean(z**2)))
            ood_p95 = float(artifact.get("ood_mahal_p95", np.inf))
            ood_p99 = float(artifact.get("ood_mahal_p99", np.inf))
            class_prior = float(artifact.get("class_prior", 0.5))
            if mahal <= ood_p95:
                adjusted_prob = raw_prob
            elif mahal >= ood_p99:
                adjusted_prob = 0.25 * raw_prob + 0.75 * class_prior
            else:
                alpha = (mahal - ood_p95) / max(1e-8, (ood_p99 - ood_p95))
                adjusted_prob = (1 - alpha) * raw_prob + alpha * (0.25 * raw_prob + 0.75 * class_prior)

            threshold = float(artifact.get("decision_threshold", 0.5))
            prediction_idx = int(adjusted_prob >= threshold)
            shap_ready, shap_message, shap_base, shap_segments, shap_plot = self._segment_shap_xai(artifact, audio_bytes)

        return VoiceInferenceResult(
            probability=float(adjusted_prob),
            raw_probability=raw_prob,
            prediction_index=prediction_idx,
            prediction_label="diabetes" if prediction_idx == 1 else "nondiabetes",
            threshold_used=threshold,
            decision_score=baseline_decision,
            ood_mahal_score=mahal,
            ood_flag=bool(mahal > ood_p99),
            shap_ready=shap_ready,
            shap_message=shap_message,
            shap_base_value=shap_base,
            shap_segments=shap_segments,
            shap_plot_base64=shap_plot,
        )
