import { Plus, MessageSquare, Utensils, Activity, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'

export default function NutritionPage() {
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Nutrition & Physical Activity</h1>
        <p className="text-muted-foreground mt-2">Track meals, nutrition, and exercise recommendations</p>
      </div>

      <Tabs defaultValue="nutrition" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-2 sm:h-10 sm:grid-cols-3 sm:gap-0">
          <TabsTrigger value="nutrition">Nutrition</TabsTrigger>
          <TabsTrigger value="exercise">Exercise</TabsTrigger>
          <TabsTrigger value="ai-coach">AI Coach</TabsTrigger>
        </TabsList>

        {/* Nutrition Tab */}
        <TabsContent value="nutrition" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Log Meal Buttons */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Log Meal</CardTitle>
                <CardDescription>Input today&apos;s meals</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button className="w-full justify-start" variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Text Input
                </Button>
                <Button className="w-full justify-start" variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Photo Upload
                </Button>
                <Button className="w-full justify-start" variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Voice Log
                </Button>
              </CardContent>
            </Card>

            {/* Daily Totals */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Today&apos;s Intake</CardTitle>
                <CardDescription>Remaining allowance</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-muted-foreground">Calories</span>
                    <span className="font-medium">1840 / 2200</span>
                  </div>
                  <Progress value={83} className="h-2" />
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-muted-foreground">Carbs</span>
                    <span className="font-medium">180g / 250g</span>
                  </div>
                  <Progress value={72} className="h-2" />
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-muted-foreground">Protein</span>
                    <span className="font-medium">65g / 80g</span>
                  </div>
                  <Progress value={81} className="h-2" />
                </div>
              </CardContent>
            </Card>

            {/* GI & GL Metrics */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Glycemic Index</CardTitle>
                <CardDescription>Daily averages</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-xs text-muted-foreground">Avg GI</p>
                  <p className="text-lg font-bold text-health-info">52</p>
                  <p className="text-xs text-health-success mt-1">Moderate - Good</p>
                </div>
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-xs text-muted-foreground">Glycemic Load</p>
                  <p className="text-lg font-bold text-primary">126</p>
                  <p className="text-xs text-muted-foreground mt-1">Within target range</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Meal History */}
          <Card>
            <CardHeader>
              <CardTitle>Today&apos;s Meals</CardTitle>
              <CardDescription>Logged nutrition entries</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="p-4 border border-border rounded-lg">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium">Breakfast</p>
                    <p className="text-sm text-muted-foreground mt-1">Oatmeal with berries, honey, and milk</p>
                  </div>
                  <span className="text-sm font-medium bg-primary/10 text-primary px-2 py-1 rounded">
                    420 cal
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Carbs: 75g</span>
                  <span>Protein: 12g</span>
                  <span>Fat: 8g</span>
                </div>
              </div>

              <div className="p-4 border border-border rounded-lg">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium">Lunch</p>
                    <p className="text-sm text-muted-foreground mt-1">Grilled chicken salad with olive oil dressing</p>
                  </div>
                  <span className="text-sm font-medium bg-primary/10 text-primary px-2 py-1 rounded">
                    520 cal
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Carbs: 35g</span>
                  <span>Protein: 38g</span>
                  <span>Fat: 22g</span>
                </div>
              </div>

              <div className="p-4 border border-border rounded-lg">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium">Snack</p>
                    <p className="text-sm text-muted-foreground mt-1">Apple with almond butter</p>
                  </div>
                  <span className="text-sm font-medium bg-primary/10 text-primary px-2 py-1 rounded">
                    200 cal
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Carbs: 25g</span>
                  <span>Protein: 8g</span>
                  <span>Fat: 7g</span>
                </div>
              </div>

              <div className="p-4 border border-border rounded-lg">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium">Dinner</p>
                    <p className="text-sm text-muted-foreground mt-1">Salmon with broccoli and brown rice</p>
                  </div>
                  <span className="text-sm font-medium bg-primary/10 text-primary px-2 py-1 rounded">
                    700 cal
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Carbs: 55g</span>
                  <span>Protein: 42g</span>
                  <span>Fat: 18g</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Exercise Tab */}
        <TabsContent value="exercise" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Exercise Recommendations</CardTitle>
              <CardDescription>Personalized activity plan based on health profile</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 border border-border rounded-lg">
                  <Activity className="h-6 w-6 text-health-success mb-2" />
                  <p className="font-medium">Walking</p>
                  <p className="text-sm text-muted-foreground mt-1">30 mins daily</p>
                  <p className="text-xs text-health-success mt-2">Low impact, ideal for maintenance</p>
                </div>

                <div className="p-4 border border-border rounded-lg">
                  <Activity className="h-6 w-6 text-health-info mb-2" />
                  <p className="font-medium">Swimming</p>
                  <p className="text-sm text-muted-foreground mt-1">2x per week</p>
                  <p className="text-xs text-health-info mt-2">Cardiovascular conditioning</p>
                </div>

                <div className="p-4 border border-border rounded-lg">
                  <Activity className="h-6 w-6 text-primary mb-2" />
                  <p className="font-medium">Resistance Training</p>
                  <p className="text-sm text-muted-foreground mt-1">2x per week</p>
                  <p className="text-xs text-muted-foreground mt-2">Light weights, muscle toning</p>
                </div>
              </div>

              <div className="p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-3">Weekly Activity Log</h4>
                <div className="space-y-2">
                  <div className="flex flex-col gap-1 text-sm sm:flex-row sm:justify-between">
                    <span>Monday - Walking</span>
                    <span className="text-muted-foreground">32 mins, 2.1 km</span>
                  </div>
                  <div className="flex flex-col gap-1 text-sm sm:flex-row sm:justify-between">
                    <span>Tuesday - Swimming</span>
                    <span className="text-muted-foreground">45 mins, 1200m</span>
                  </div>
                  <div className="flex flex-col gap-1 text-sm sm:flex-row sm:justify-between">
                    <span>Wednesday - Walking</span>
                    <span className="text-muted-foreground">28 mins, 1.9 km</span>
                  </div>
                  <div className="flex flex-col gap-1 text-sm sm:flex-row sm:justify-between">
                    <span>Thursday - Rest Day</span>
                    <span className="text-muted-foreground">Light stretching</span>
                  </div>
                  <div className="flex flex-col gap-1 text-sm sm:flex-row sm:justify-between">
                    <span>Friday - Resistance</span>
                    <span className="text-muted-foreground">35 mins, 8 exercises</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* AI Coach Tab */}
        <TabsContent value="ai-coach" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>AI Nutrition Coach</CardTitle>
              <CardDescription>Chat with your personal AI health assistant</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="h-96 border border-border rounded-lg bg-muted/30 p-4 flex flex-col">
                <div className="flex-1 space-y-4 overflow-y-auto mb-4">
                  <div className="flex justify-start">
                    <div className="bg-primary/10 text-primary px-4 py-2 rounded-lg max-w-xs">
                      <p className="text-sm">Hello! I&apos;m your nutrition coach. How can I help you today?</p>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <div className="bg-primary text-primary-foreground px-4 py-2 rounded-lg max-w-xs">
                      <p className="text-sm">What should I eat for dinner?</p>
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="bg-primary/10 text-primary px-4 py-2 rounded-lg max-w-sm">
                      <p className="text-sm">Based on your daily intake and health goals, I recommend a balanced meal with lean protein, whole grains, and vegetables. How about grilled salmon with quinoa?</p>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Ask me anything about nutrition..."
                    className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-sm"
                  />
                  <Button size="icon">
                    <MessageSquare className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
