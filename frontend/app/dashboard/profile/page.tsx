'use client'

import { useEffect, useRef, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { useAuth } from '@/components/auth-context'
import { updateUserProfile, uploadProfilePicture } from '@/lib/auth'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Loader2, Camera, User as UserIcon, Heart, Activity, Mail, Calendar } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

export default function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    height_cm: '',
    weight_kg: '',
    date_of_birth: '',
    gender: '',
    smoking_status: '',
    hypertension: false,
    heart_disease: false,
    hba1c_level: '',
    blood_glucose_level: '',
  })

  useEffect(() => {
    if (user) {
      setFormData({
        first_name: user.full_name?.split(' ')[0] || '',
        last_name: user.full_name?.split(' ').slice(1).join(' ') || '',
        email: user.email || '',
        height_cm: user.height_cm?.toString() || '',
        weight_kg: user.weight_kg?.toString() || '',
        date_of_birth: user.date_of_birth || '',
        gender: user.gender || '',
        smoking_status: user.smoking_status || '',
        hypertension: !!user.hypertension,
        heart_disease: !!user.heart_disease,
        hba1c_level: user.hba1c_level?.toString() || '',
        blood_glucose_level: user.blood_glucose_level?.toString() || '',
      })
    }
  }, [user])

  const handleSave = async () => {
    setLoading(true)
    try {
      await updateUserProfile({
        ...formData,
        height_cm: formData.height_cm ? parseFloat(formData.height_cm) : null,
        weight_kg: formData.weight_kg ? parseFloat(formData.weight_kg) : null,
        hba1c_level: formData.hba1c_level ? parseFloat(formData.hba1c_level) : null,
        blood_glucose_level: formData.blood_glucose_level ? parseInt(formData.blood_glucose_level) : null,
      } as any)
      await refreshUser()
      toast.success('Profile updated successfully')
    } catch (err) {
      console.error(err)
      toast.error('Failed to update profile')
    } finally {
      setLoading(false)
    }
  }

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadingPicture, setUploadingPicture] = useState(false)

  const handlePictureUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingPicture(true)
    try {
      await uploadProfilePicture(file)
      await refreshUser()
      toast.success('Profile picture updated!')
    } catch (err) {
      console.error(err)
      toast.error('Failed to upload picture')
    } finally {
      setUploadingPicture(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6 p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">My Profile</h1>
          <p className="text-muted-foreground mt-1">Manage your account and health metrics</p>
        </div>
        <Button onClick={handleSave} disabled={loading} className="w-full sm:w-auto shadow-lg shadow-primary/20">
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Changes
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Avatar & Summary */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="text-center">
            <CardContent className="pt-8 space-y-4">
              <div className="relative inline-block">
                <Avatar className="h-24 w-24 border-4 border-background shadow-xl mx-auto">
                  <AvatarImage src={user?.profile_picture || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username}`} />
                  <AvatarFallback>{user?.username?.[0].toUpperCase()}</AvatarFallback>
                </Avatar>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handlePictureUpload}
                />
                <Button 
                  size="icon" 
                  variant="secondary" 
                  className="absolute bottom-0 right-0 rounded-full h-8 w-8 shadow-md"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingPicture}
                >
                  {uploadingPicture ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                </Button>
              </div>
              <div>
                <h2 className="text-xl font-bold">{user?.full_name || user?.username}</h2>
                <p className="text-sm text-muted-foreground capitalize">{user?.role} Profile</p>
              </div>
              <div className="flex justify-center gap-2">
                <Badge variant="outline">{user?.diabetes_type || 'Type 2'}</Badge>
                <Badge variant="outline" className="text-health-info border-health-info/30 bg-health-info/5">
                  BMI: {((parseFloat(formData.weight_kg) || 0) / Math.pow((parseFloat(formData.height_cm) || 100) / 100, 2)).toFixed(1)}
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Account Quick-Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center gap-3 text-muted-foreground">
                <Mail className="h-4 w-4" />
                <span className="truncate">{user?.email}</span>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground">
                <Calendar className="h-4 w-4" />
                <span>Joined April 2026</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Detailed Info */}
        <div className="lg:col-span-2">
          <Tabs defaultValue="personal" className="w-full">
            <TabsList className="w-full justify-start border-b rounded-none h-auto p-0 bg-transparent mb-6">
              <TabsTrigger 
                value="personal" 
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-3"
              >
                Personal Info
              </TabsTrigger>
              <TabsTrigger 
                value="health" 
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-3"
              >
                Health & Clinical
              </TabsTrigger>
            </TabsList>

            <TabsContent value="personal" className="mt-0 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Basic Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="firstName">First Name</Label>
                      <Input 
                        id="firstName" 
                        value={formData.first_name} 
                        onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="lastName">Last Name</Label>
                      <Input 
                        id="lastName" 
                        value={formData.last_name} 
                        onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2 lg:col-span-2">
                      <Label htmlFor="email">Email Address</Label>
                      <Input 
                        id="email" 
                        type="email" 
                        value={formData.email} 
                        onChange={(e) => setFormData({...formData, email: e.target.value})}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Physical Metrics</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="height_p">Height (cm)</Label>
                      <Input 
                        id="height_p" 
                        type="number" 
                        value={formData.height_cm} 
                        onChange={(e) => setFormData({...formData, height_cm: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="weight_p">Weight (kg)</Label>
                      <Input 
                        id="weight_p" 
                        type="number" 
                        value={formData.weight_kg} 
                        onChange={(e) => setFormData({...formData, weight_kg: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="gender_p">Gender</Label>
                      <Select value={formData.gender} onValueChange={(v) => setFormData({...formData, gender: v})}>
                        <SelectTrigger id="gender_p">
                          <SelectValue placeholder="Select gender" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Male">Male</SelectItem>
                          <SelectItem value="Female">Female</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="dob_p">Date of Birth</Label>
                      <Input 
                        id="dob_p" 
                        type="date" 
                        value={formData.date_of_birth} 
                        onChange={(e) => setFormData({...formData, date_of_birth: e.target.value})}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="health" className="mt-0 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-blue-500" />
                    Clinical History
                  </CardTitle>
                  <CardDescription>Important metrics for diabetes risk management</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="hba1c_p">HbA1c Level (%)</Label>
                      <Input 
                        id="hba1c_p" 
                        type="number" 
                        step="0.1" 
                        value={formData.hba1c_level} 
                        onChange={(e) => setFormData({...formData, hba1c_level: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="glucose_p">Blood Glucose (mg/dL)</Label>
                      <Input 
                        id="glucose_p" 
                        type="number" 
                        value={formData.blood_glucose_level} 
                        onChange={(e) => setFormData({...formData, blood_glucose_level: e.target.value})}
                      />
                    </div>
                  </div>

                  <div className="space-y-4 pt-4 border-t">
                    <h4 className="text-sm font-semibold flex items-center gap-2">
                      <Heart className="h-4 w-4 text-red-500" />
                      Condition Toggles
                    </h4>
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="space-y-0.5">
                        <Label>Hypertension</Label>
                        <p className="text-xs text-muted-foreground">Diagnosed high blood pressure</p>
                      </div>
                      <Switch 
                        checked={formData.hypertension} 
                        onCheckedChange={(checked) => setFormData({...formData, hypertension: checked})}
                      />
                    </div>
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="space-y-0.5">
                        <Label>Heart Disease</Label>
                        <p className="text-xs text-muted-foreground">History of cardiovascular conditions</p>
                      </div>
                      <Switch 
                        checked={formData.heart_disease} 
                        onCheckedChange={(checked) => setFormData({...formData, heart_disease: checked})}
                      />
                    </div>
                  </div>

                  <div className="space-y-2 pt-4 border-t">
                    <Label htmlFor="smoking_p">Smoking Status</Label>
                    <Select value={formData.smoking_status} onValueChange={(v) => setFormData({...formData, smoking_status: v})}>
                      <SelectTrigger id="smoking_p">
                        <SelectValue placeholder="Select status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="never">Never Smoked</SelectItem>
                        <SelectItem value="former">Former Smoker</SelectItem>
                        <SelectItem value="current">Current Smoker</SelectItem>
                        <SelectItem value="not current">Not Current</SelectItem>
                        <SelectItem value="No Info">No Information</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
