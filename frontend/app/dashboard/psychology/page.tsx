import { MessageCircle, BarChart3, Heart, Zap } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

export default function PsychologyPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Psychology & Mental Wellness</h1>
        <p className="text-muted-foreground mt-2">AI-powered emotional health tracking and therapy sessions</p>
      </div>

      {/* Emotional Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Current Mood</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-full bg-psychology-soft-purple/20 flex items-center justify-center">
                <Heart className="h-6 w-6 text-psychology-soft-purple" />
              </div>
              <div>
                <p className="text-lg font-bold">Calm</p>
                <p className="text-xs text-muted-foreground">Stable emotions</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Stress Level</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-health-warning">38%</div>
              <div className="flex-1">
                <Progress value={38} className="h-2" />
                <p className="text-xs text-muted-foreground mt-1">Moderate stress</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Sleep Quality</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-health-success">7.5h</div>
              <div className="flex-1">
                <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                  Excellent
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Wellness Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-primary">72</div>
              <div className="flex-1">
                <Progress value={72} className="h-2" />
                <p className="text-xs text-muted-foreground mt-1">Good overall</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* AI Therapy Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5 text-psychology-soft-purple" />
              AI Therapy Session
            </CardTitle>
            <CardDescription>Chat with your AI therapist</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-80 border border-border rounded-lg bg-muted/30 p-4 flex flex-col">
              <div className="flex-1 space-y-4 overflow-y-auto mb-4">
                <div className="flex justify-start">
                  <div className="bg-psychology-soft-purple/10 text-psychology-soft-purple px-4 py-2 rounded-lg max-w-xs">
                    <p className="text-sm">Good morning. How are you feeling today?</p>
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="bg-primary text-primary-foreground px-4 py-2 rounded-lg max-w-xs">
                    <p className="text-sm">I&apos;m feeling a bit overwhelmed with work</p>
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="bg-psychology-soft-purple/10 text-psychology-soft-purple px-4 py-2 rounded-lg max-w-sm">
                    <p className="text-sm">I understand. Let&apos;s work through this together. Can you tell me what specifically is causing the overwhelm? Sometimes breaking things down helps.</p>
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="bg-primary text-primary-foreground px-4 py-2 rounded-lg max-w-xs">
                    <p className="text-sm">There are too many deadlines this week</p>
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="bg-psychology-soft-purple/10 text-psychology-soft-purple px-4 py-2 rounded-lg max-w-sm">
                    <p className="text-sm">Have you tried prioritizing tasks by urgency and importance? I can help you create a manageable plan.</p>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Share your thoughts..."
                  className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-sm"
                />
                <Button size="icon">
                  <MessageCircle className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Wellness Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Quick Wellness
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" className="w-full justify-start text-left h-auto py-3">
              <div>
                <p className="font-medium text-sm">Guided Meditation</p>
                <p className="text-xs text-muted-foreground">10 min • Stress relief</p>
              </div>
            </Button>
            <Button variant="outline" className="w-full justify-start text-left h-auto py-3">
              <div>
                <p className="font-medium text-sm">Deep Breathing</p>
                <p className="text-xs text-muted-foreground">5 min • Instant calm</p>
              </div>
            </Button>
            <Button variant="outline" className="w-full justify-start text-left h-auto py-3">
              <div>
                <p className="font-medium text-sm">Journaling Prompt</p>
                <p className="text-xs text-muted-foreground">15 min • Self-reflection</p>
              </div>
            </Button>
            <Button variant="outline" className="w-full justify-start text-left h-auto py-3">
              <div>
                <p className="font-medium text-sm">Gratitude Exercise</p>
                <p className="text-xs text-muted-foreground">5 min • Mood boost</p>
              </div>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Emotional Trends */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Emotional State Trends
          </CardTitle>
          <CardDescription>Weekly mood and stress patterns</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium">Happiness</span>
                <span className="text-sm text-muted-foreground">72/100</span>
              </div>
              <div className="grid grid-cols-7 gap-2">
                {[65, 70, 68, 72, 75, 78, 72].map((value, idx) => (
                  <div key={idx} className="flex flex-col items-center">
                    <div
                      className="w-full bg-health-success rounded-sm"
                      style={{ height: `${value / 100 * 60}px` }}
                    />
                    <p className="text-xs text-muted-foreground mt-1">Mon</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium">Anxiety</span>
                <span className="text-sm text-muted-foreground">35/100</span>
              </div>
              <div className="grid grid-cols-7 gap-2">
                {[42, 38, 40, 35, 32, 30, 35].map((value, idx) => (
                  <div key={idx} className="flex flex-col items-center">
                    <div
                      className="w-full bg-health-warning rounded-sm"
                      style={{ height: `${value / 100 * 60}px` }}
                    />
                    <p className="text-xs text-muted-foreground mt-1">Mon</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium">Energy Level</span>
                <span className="text-sm text-muted-foreground">68/100</span>
              </div>
              <div className="grid grid-cols-7 gap-2">
                {[60, 65, 62, 68, 70, 75, 68].map((value, idx) => (
                  <div key={idx} className="flex flex-col items-center">
                    <div
                      className="w-full bg-primary rounded-sm"
                      style={{ height: `${value / 100 * 60}px` }}
                    />
                    <p className="text-xs text-muted-foreground mt-1">Mon</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
