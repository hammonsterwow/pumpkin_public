import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { Gift, Star, Coffee, Users, Crown, Award } from 'lucide-react';

interface LoyaltyProgramProps {
  onNavigate: (screen: string, data?: any) => void;
}

export function LoyaltyProgram({ onNavigate }: LoyaltyProgramProps) {
  const userPoints = 350;
  const nextTierPoints = 500;
  const progress = (userPoints / nextTierPoints) * 100;

  const rewards = [
    { id: 1, title: 'Free Coffee Bag', points: 200, available: true },
    { id: 2, title: '10% Discount', points: 150, available: true },
    { id: 3, title: 'Premium Gift Set', points: 500, available: false },
    { id: 4, title: 'Farmer Visit Experience', points: 1000, available: false }
  ];

  const activities = [
    { action: 'Purchase coffee', points: '+25 points', date: '2 days ago' },
    { action: 'Referral bonus', points: '+50 points', date: '1 week ago' },
    { action: 'Review product', points: '+10 points', date: '2 weeks ago' },
    { action: 'Social media share', points: '+5 points', date: '3 weeks ago' }
  ];

  return (
    <div className="pb-20 bg-background min-h-screen">
      {/* Header */}
      <div className="bg-primary text-primary-foreground p-6 rounded-b-2xl">
        <div className="flex items-center gap-3 mb-4">
          <Crown className="h-8 w-8" />
          <div>
            <h1 className="text-xl font-semibold">Coffee Loyalty</h1>
            <p className="opacity-90">Your journey with every cup</p>
          </div>
        </div>
        
        {/* Points Display */}
        <Card className="bg-primary-foreground text-primary">
          <CardContent className="p-4">
            <div className="flex justify-between items-center mb-2">
              <span>Current Points</span>
              <span className="text-2xl font-semibold">{userPoints}</span>
            </div>
            <Progress value={progress} className="mb-2" />
            <p className="text-sm opacity-80">
              {nextTierPoints - userPoints} points to Gold tier
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="p-4 space-y-6">
        {/* Tier Benefits */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="h-5 w-5 text-accent" />
              Current Tier: Silver
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Coffee className="h-4 w-4 text-primary" />
                <span>5% discount on all purchases</span>
              </div>
              <div className="flex items-center gap-2">
                <Gift className="h-4 w-4 text-primary" />
                <span>Birthday bonus: 50 points</span>
              </div>
              <div className="flex items-center gap-2">
                <Star className="h-4 w-4 text-primary" />
                <span>Early access to new arrivals</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Available Rewards */}
        <div>
          <h2 className="mb-4">Available Rewards</h2>
          <div className="space-y-3">
            {rewards.map((reward) => (
              <Card key={reward.id} className={!reward.available ? 'opacity-50' : ''}>
                <CardContent className="p-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="font-medium">{reward.title}</h3>
                      <p className="text-sm text-muted-foreground">{reward.points} points</p>
                    </div>
                    <Button 
                      size="sm" 
                      disabled={!reward.available || userPoints < reward.points}
                    >
                      {reward.available && userPoints >= reward.points ? 'Redeem' : 'Locked'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Ways to Earn */}
        <Card>
          <CardHeader>
            <CardTitle>Ways to Earn Points</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span>Purchase coffee (per $1)</span>
                <Badge variant="secondary">1 point</Badge>
              </div>
              <div className="flex justify-between">
                <span>Write a review</span>
                <Badge variant="secondary">10 points</Badge>
              </div>
              <div className="flex justify-between">
                <span>Refer a friend</span>
                <Badge variant="secondary">50 points</Badge>
              </div>
              <div className="flex justify-between">
                <span>Social media share</span>
                <Badge variant="secondary">5 points</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <div>
          <h2 className="mb-4">Recent Activity</h2>
          <div className="space-y-3">
            {activities.map((activity, index) => (
              <Card key={index}>
                <CardContent className="p-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="font-medium text-sm">{activity.action}</p>
                      <p className="text-xs text-muted-foreground">{activity.date}</p>
                    </div>
                    <span className="text-sm text-accent font-medium">{activity.points}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Join Community */}
        <Card className="bg-accent text-accent-foreground">
          <CardContent className="p-4 text-center">
            <Users className="h-8 w-8 mx-auto mb-2" />
            <h3 className="font-medium mb-2">Join Our Coffee Community</h3>
            <p className="text-sm mb-3">Connect with fellow coffee lovers and earn bonus points</p>
            <Button variant="secondary" className="w-full">
              Join Community
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}