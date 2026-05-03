import { getApiUrls } from '@/lib/auth'

export interface CataractProbabilities {
  [key: string]: number
}

export interface CataractInferenceResponse {
  patient_id: number
  prediction_index: number
  prediction_label: string
  confidence: number
  p_cataract: number
  probabilities: CataractProbabilities
  model_name: string
  model_version: string
}

/**
 * Submit eye image for cataract detection
 */
export async function inferCataract(imageFile: File): Promise<CataractInferenceResponse> {
  const { fastapi } = getApiUrls()
  const formData = new FormData()
  formData.append('image', imageFile)

  const response = await fetch(`${fastapi}/screening/cataract/infer`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Cataract inference failed: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Get cataract model health status
 */
export async function getCataractModelHealth() {
  const { fastapi } = getApiUrls()
  const response = await fetch(`${fastapi}/screening/cataract/health`, {
    credentials: 'include',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to fetch model health')
  }

  return response.json()
}
