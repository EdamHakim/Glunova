'use client'

import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Plus, Loader2, Camera, CheckCircle2, AlertCircle } from 'lucide-react'
import { analyseNutritionPhoto, logMeal, NutritionAnalysisReport } from '@/lib/nutrition-api'
import { useAuth } from '@/components/auth-context'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { toast } from 'sonner'

export function NutritionAnalysisModal({ disabled, onLogged }: { disabled?: boolean; onLogged?: () => void }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<NutritionAnalysisReport | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setResult(null)
    }
  }

  const handleAnalyze = async () => {
    if (!file || !user) return

    setLoading(true)
    try {
      // Build profile from user context
      const profile = {
        age: user.age || 30,
        weight_kg: user.weight_kg || 70,
        height_cm: user.height_cm || 170,
        diabetes_type: user.diabetes_type || 'Type 2',
        medication: user.medication || [],
        last_glucose: user.last_glucose || '100 mg/dL',
        carb_limit_per_meal_g: user.carb_limit_per_meal_g || 60,
      }

      const report = await analyseNutritionPhoto(file, profile)
      setResult(report)
      toast.success('Analysis complete!')
    } catch (error) {
      console.error(error)
      toast.error('Analysis failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!result || !user) return
    setSaving(true)
    try {
      // Helper to parse numeric values from LLM strings like "approx 450 kcal"
      const parseValue = (s: string) => parseFloat(s.replace(/[^0-9.]/g, '')) || 0
      const giMap: Record<string, number> = { low: 30, medium: 55, high: 80 }
      
      const avgGi = result.analyse_nutritionnelle.ingredients_analysis.length > 0
        ? result.analyse_nutritionnelle.ingredients_analysis.reduce((acc, ing) => acc + (giMap[ing.gi.toLowerCase()] || 40), 0) / result.analyse_nutritionnelle.ingredients_analysis.length
        : 40

      await logMeal({
        input_type: 'photo',
        description: result.plat_identifie,
        calories_kcal: parseValue(result.analyse_nutritionnelle.global_assessment.total_calories),
        carbs_g: result.analyse_nutritionnelle.ingredients_analysis.length * 15, // Rough estimate if not in GL
        sugar_g: 0, // LLM doesn't explicitly return sugar yet
        gi: avgGi,
        gl: giMap[result.analyse_nutritionnelle.global_assessment.total_glycemic_load.toLowerCase()] || 15
      })
      toast.success('Meal logged successfully!')
      setOpen(false)
      if (onLogged) onLogged()
    } catch (error) {
      console.error(error)
      toast.error('Failed to log meal.')
    } finally {
      setSaving(false)
    }
  }

  const riskColors = {
    green: 'bg-green-500/10 text-green-500 border-green-500/20',
    orange: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
    red: 'bg-red-500/10 text-red-500 border-red-500/20',
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="w-full justify-start" variant="outline" disabled={disabled}>
          <Plus className="h-4 w-4 mr-2" />
          Photo Upload
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5 text-primary" />
            AI Nutrition Analysis
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {!result && (
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-muted-foreground/20 rounded-xl p-12 bg-muted/5 transition-colors hover:bg-muted/10">
              <input
                type="file"
                accept="image/*"
                className="hidden"
                id="food-upload"
                onChange={handleFileChange}
              />
              <label
                htmlFor="food-upload"
                className="flex flex-col items-center gap-4 cursor-pointer text-center"
              >
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <Plus className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <p className="font-medium">{file ? file.name : 'Select Food Photo'}</p>
                  <p className="text-sm text-muted-foreground mt-1">Upload a clear photo of your meal</p>
                </div>
              </label>
            </div>
          )}

          {file && !result && (
            <Button
              className="w-full h-12 text-lg font-semibold shadow-lg shadow-primary/20"
              onClick={handleAnalyze}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Analyzing Dish...
                </>
              ) : (
                'Start AI Analysis'
              )}
            </Button>
          )}

          {result && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {/* Header Card */}
              <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-background to-muted/30 p-6 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <Badge variant="outline" className="mb-2 uppercase tracking-wider text-[10px]">
                      Identified Dish
                    </Badge>
                    <h3 className="text-2xl font-bold text-foreground capitalize">
                      {result.plat_identifie}
                    </h3>
                  </div>
                  <Badge className={riskColors[result.analyse_nutritionnelle.global_assessment.risk_level]}>
                    {result.analyse_nutritionnelle.global_assessment.risk_level.toUpperCase()} RISK
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground italic">
                  "{result.analyse_nutritionnelle.summary}"
                </p>
              </div>

              {/* Nutrition Grid */}
              <div className="grid grid-cols-2 gap-4">
                <Card className="bg-muted/10 border-none">
                  <CardContent className="pt-6">
                    <p className="text-xs text-muted-foreground uppercase font-semibold">Calories</p>
                    <p className="text-2xl font-bold">{result.analyse_nutritionnelle.global_assessment.total_calories}</p>
                  </CardContent>
                </Card>
                <Card className="bg-muted/10 border-none">
                  <CardContent className="pt-6">
                    <p className="text-xs text-muted-foreground uppercase font-semibold">Glycemic Load</p>
                    <p className="text-2xl font-bold">{result.analyse_nutritionnelle.global_assessment.total_glycemic_load}</p>
                  </CardContent>
                </Card>
              </div>

              {/* Ingredients */}
              <div className="space-y-3">
                <h4 className="font-semibold text-sm flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-primary" />
                  Detected Ingredients
                </h4>
                <div className="grid grid-cols-1 gap-2">
                  {result.analyse_nutritionnelle.ingredients_analysis.map((ing, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/5">
                      <div>
                        <p className="font-medium text-sm">{ing.ingredient}</p>
                        <p className="text-[10px] text-muted-foreground">{ing.benefit}</p>
                      </div>
                      <Badge variant="secondary" className="text-[10px]">GI: {ing.gi}</Badge>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recommendations */}
              <div className="p-4 rounded-xl bg-primary/5 border border-primary/10 space-y-3">
                <h4 className="font-semibold text-sm flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-primary" />
                  AI Recommendations
                </h4>
                <ul className="text-sm space-y-2">
                  {result.analyse_nutritionnelle.recommendations.map((rec, idx) => (
                    <li key={idx} className="flex gap-2">
                      <span className="text-primary">•</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="flex gap-3">
                <Button variant="outline" className="flex-1" onClick={() => { setFile(null); setResult(null); }}>
                  Analyze Another
                </Button>
                <Button className="flex-1" onClick={handleSave} disabled={saving}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
                  Save to Log
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
