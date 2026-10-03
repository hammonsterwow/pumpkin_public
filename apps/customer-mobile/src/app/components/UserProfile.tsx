import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Progress } from './ui/progress';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { 
  User, Mail, Phone, MapPin, Calendar, Star, Package, 
  Coffee, Crown, Gift, Edit, Save, X, Camera, 
  CreditCard, Truck, Settings, LogOut, ArrowLeft, Users 
} from 'lucide-react';

interface UserProfileProps {
  user: any;
  onNavigate: (screen: string, data?: any) => void;
  onUpdateUser: (user: any) => void;
  onLogout: () => void;
  isMobile: boolean;
}

export function UserProfile({ user, onNavigate, onUpdateUser, onLogout, isMobile }: UserProfileProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({
    name: user.name,
    email: user.email,
    phone: user.phone || '',
    address: user.address || ''
  });

  const orders = [
    {
      id: 'ICO001',
      date: '2024-01-15',
      status: 'delivered',
      total: 67.98,
      items: [
        { name: 'Nyagatare Single Origin', quantity: 2, price: 24.99 },
        { name: 'Kivu Lake Reserve', quantity: 1, price: 28.99 }
      ]
    },
    {
      id: 'ICO002',
      date: '2024-01-08',
      status: 'shipped',
      total: 45.98,
      items: [
        { name: 'Musanze Mountain Blend', quantity: 2, price: 22.99 }
      ]
    },
    {
      id: 'ICO003',
      date: '2024-01-02',
      status: 'processing',
      total: 89.97,
      items: [
        { name: 'Huye Honey Process', quantity: 3, price: 26.99 }
      ]
    }
  ];

  const subscriptions = [
    {
      id: 'SUB001',
      name: 'Monthly Discovery Box',
      nextDelivery: '2024-02-15',
      status: 'active',
      frequency: 'Monthly',
      products: ['Nyagatare Single Origin', 'Seasonal Selection']
    },
    {
      id: 'SUB002',
      name: 'Weekly Essentials',
      nextDelivery: '2024-02-05',
      status: 'paused',
      frequency: 'Weekly',
      products: ['Musanze Mountain Blend']
    }
  ];

  const loyaltyActivity = [
    { date: '2024-01-15', action: 'Purchase', points: '+25', description: 'Order ICO001' },
    { date: '2024-01-10', action: 'Review', points: '+10', description: 'Reviewed Kivu Lake Reserve' },
    { date: '2024-01-08', action: 'Purchase', points: '+23', description: 'Order ICO002' },
    { date: '2024-01-05', action: 'Referral', points: '+50', description: 'Friend joined' }
  ];

  const tierBenefits = {
    Bronze: ['5% off orders', 'Birthday reward'],
    Silver: ['10% off orders', 'Free shipping on $50+', 'Early access to new products'],
    Gold: ['15% off orders', 'Free shipping always', 'Exclusive products', 'Priority support'],
    Platinum: ['20% off orders', 'Free shipping always', 'VIP experiences', 'Personal coffee consultant']
  };

  const nextTierPoints = user.tier === 'Bronze' ? 200 : user.tier === 'Silver' ? 500 : user.tier === 'Gold' ? 1000 : 2000;
  const currentTierMin = user.tier === 'Bronze' ? 0 : user.tier === 'Silver' ? 200 : user.tier === 'Gold' ? 500 : 1000;
  const progress = ((user.loyaltyPoints - currentTierMin) / (nextTierPoints - currentTierMin)) * 100;

  const handleSaveProfile = () => {
    onUpdateUser({ ...user, ...editData });
    setIsEditing(false);
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      delivered: { variant: 'default' as const, label: 'Delivered' },
      shipped: { variant: 'secondary' as const, label: 'Shipped' },
      processing: { variant: 'outline' as const, label: 'Processing' },
      active: { variant: 'default' as const, label: 'Active' },
      paused: { variant: 'secondary' as const, label: 'Paused' }
    };
    
    const config = statusConfig[status as keyof typeof statusConfig];
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  return (
    <div className={`bg-background min-h-screen ${isMobile ? 'pb-20' : ''}`}>
      {/* Header */}
      <div className="bg-card border-b border-border">
        <div className={`${isMobile ? 'p-4' : 'max-w-7xl mx-auto px-6 py-6'}`}>
          <div className="flex items-center justify-between">
            {isMobile && (
              <Button variant="ghost" size="sm" onClick={() => onNavigate('home')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            )}
            <h1 className={`${isMobile ? 'text-lg' : 'text-xl'} font-semibold`}>My Account</h1>
            <Button variant="ghost" size="sm" onClick={onLogout}>
              <LogOut className="h-4 w-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </div>
      </div>

      <div className={`${isMobile ? 'p-4' : 'max-w-7xl mx-auto px-6 py-8'}`}>
        {/* Profile Header */}
        <Card className="mb-8">
          <CardContent className="p-6">
            <div className={`flex ${isMobile ? 'flex-col items-center text-center' : 'items-center'} gap-6`}>
              <div className="relative">
                <div className="w-20 h-20 bg-gradient-to-br from-primary to-primary/80 rounded-full flex items-center justify-center">
                  {user.avatar ? (
                    <ImageWithFallback
                      src={user.avatar}
                      alt={user.name}
                      className="w-20 h-20 rounded-full object-cover"
                    />
                  ) : (
                    <span className="text-primary-foreground text-2xl font-semibold">
                      {user.name.split(' ').map((n: string) => n[0]).join('')}
                    </span>
                  )}
                </div>
                <button className="absolute bottom-0 right-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center">
                  <Camera className="h-3 w-3" />
                </button>
              </div>
              
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="text-xl font-semibold">{user.name}</h2>
                  <div className="flex items-center gap-1">
                    <Crown className="h-4 w-4 text-gold" />
                    <Badge className="bg-gold text-gold-foreground">{user.tier}</Badge>
                  </div>
                </div>
                <p className="text-muted-foreground mb-3">{user.email}</p>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    <span>Member since {new Date(user.joinDate).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Star className="h-3 w-3 text-gold" />
                    <span>{user.loyaltyPoints} points</span>
                  </div>
                </div>
              </div>
              
              {!isMobile && (
                <Button variant="outline" onClick={() => setIsEditing(true)}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit Profile
                </Button>
              )}
            </div>

            {/* Loyalty Progress */}
            <div className="mt-6 p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Progress to {user.tier === 'Platinum' ? 'Platinum' : 'next tier'}</span>
                <span className="text-sm text-muted-foreground">
                  {user.loyaltyPoints}/{nextTierPoints} points
                </span>
              </div>
              <Progress value={user.tier === 'Platinum' ? 100 : progress} className="mb-2" />
              <p className="text-xs text-muted-foreground">
                {user.tier === 'Platinum' 
                  ? 'You\'ve reached our highest tier!'
                  : `${nextTierPoints - user.loyaltyPoints} points to reach ${user.tier === 'Bronze' ? 'Silver' : user.tier === 'Silver' ? 'Gold' : 'Platinum'} tier`
                }
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs defaultValue="profile" className="w-full">
          <TabsList className={`grid w-full ${isMobile ? 'grid-cols-2' : 'grid-cols-4'}`}>
            <TabsTrigger value="profile">Profile</TabsTrigger>
            <TabsTrigger value="orders">Orders</TabsTrigger>
            <TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
            <TabsTrigger value="loyalty">Loyalty</TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="mt-6">
            <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2'} gap-6`}>
              {/* Personal Information */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Personal Information
                  </CardTitle>
                  {!isEditing && (
                    <Button variant="ghost" size="sm" onClick={() => setIsEditing(true)}>
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  {isEditing ? (
                    <>
                      <div>
                        <Label htmlFor="name">Full Name</Label>
                        <Input
                          id="name"
                          value={editData.name}
                          onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="email">Email</Label>
                        <Input
                          id="email"
                          type="email"
                          value={editData.email}
                          onChange={(e) => setEditData({ ...editData, email: e.target.value })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="phone">Phone</Label>
                        <Input
                          id="phone"
                          value={editData.phone}
                          onChange={(e) => setEditData({ ...editData, phone: e.target.value })}
                          placeholder="+250 xxx xxx xxx"
                        />
                      </div>
                      <div>
                        <Label htmlFor="address">Address</Label>
                        <Input
                          id="address"
                          value={editData.address}
                          onChange={(e) => setEditData({ ...editData, address: e.target.value })}
                          placeholder="Your address"
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={handleSaveProfile} size="sm">
                          <Save className="h-4 w-4 mr-2" />
                          Save
                        </Button>
                        <Button variant="outline" onClick={() => setIsEditing(false)} size="sm">
                          <X className="h-4 w-4 mr-2" />
                          Cancel
                        </Button>
                      </div>
                    </>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span>{user.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <Mail className="h-4 w-4 text-muted-foreground" />
                        <span>{user.email}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <Phone className="h-4 w-4 text-muted-foreground" />
                        <span>{user.phone || 'Not provided'}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <MapPin className="h-4 w-4 text-muted-foreground" />
                        <span>{user.address || 'Not provided'}</span>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Tier Benefits */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Crown className="h-5 w-5 text-gold" />
                    {user.tier} Tier Benefits
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {tierBenefits[user.tier as keyof typeof tierBenefits]?.map((benefit, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <Gift className="h-4 w-4 text-primary" />
                        <span className="text-sm">{benefit}</span>
                      </div>
                    ))}
                  </div>
                  <Button 
                    variant="outline" 
                    className="w-full mt-4"
                    onClick={() => onNavigate('loyalty')}
                  >
                    View Loyalty Program
                  </Button>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="orders" className="mt-6">
            <div className="space-y-4">
              {orders.map((order) => (
                <Card key={order.id} className="transition-premium hover-lift">
                  <CardContent className="p-6">
                    <div className={`flex ${isMobile ? 'flex-col' : 'items-center justify-between'} gap-4`}>
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <Package className="h-5 w-5 text-primary" />
                          <span className="font-medium">Order #{order.id}</span>
                          {getStatusBadge(order.status)}
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">
                          Placed on {new Date(order.date).toLocaleDateString()}
                        </p>
                        <div className="space-y-1">
                          {order.items.map((item, idx) => (
                            <p key={idx} className="text-sm">
                              {item.quantity}x {item.name} - ${item.price}
                            </p>
                          ))}
                        </div>
                      </div>
                      <div className={`${isMobile ? 'flex justify-between items-center' : 'text-right'}`}>
                        <div>
                          <p className="font-semibold">${order.total}</p>
                          <p className="text-sm text-muted-foreground">Total</p>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm">
                            <Truck className="h-4 w-4 mr-2" />
                            Track
                          </Button>
                          <Button size="sm">Reorder</Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="subscriptions" className="mt-6">
            <div className="space-y-4">
              {subscriptions.map((subscription) => (
                <Card key={subscription.id} className="transition-premium hover-lift">
                  <CardContent className="p-6">
                    <div className={`flex ${isMobile ? 'flex-col' : 'items-center justify-between'} gap-4`}>
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <Coffee className="h-5 w-5 text-primary" />
                          <span className="font-medium">{subscription.name}</span>
                          {getStatusBadge(subscription.status)}
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">
                          {subscription.frequency} delivery
                        </p>
                        <p className="text-sm">
                          Next delivery: {new Date(subscription.nextDelivery).toLocaleDateString()}
                        </p>
                        <div className="mt-2">
                          <span className="text-sm text-muted-foreground">Products: </span>
                          <span className="text-sm">{subscription.products.join(', ')}</span>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm">
                          <Settings className="h-4 w-4 mr-2" />
                          Manage
                        </Button>
                        <Button 
                          size="sm" 
                          variant={subscription.status === 'active' ? 'secondary' : 'default'}
                        >
                          {subscription.status === 'active' ? 'Pause' : 'Resume'}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              
              <Card className="border-dashed">
                <CardContent className="p-6 text-center">
                  <Coffee className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="font-medium mb-2">Start a Coffee Subscription</h3>
                  <p className="text-muted-foreground text-sm mb-4">
                    Never run out of your favorite coffee with automatic deliveries
                  </p>
                  <Button>Browse Subscriptions</Button>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="loyalty" className="mt-6">
            <div className="space-y-6">
              {/* Loyalty Overview */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Star className="h-5 w-5 text-gold" />
                    Loyalty Points Activity
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {loyaltyActivity.map((activity, index) => (
                      <div key={index} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                        <div>
                          <p className="text-sm font-medium">{activity.action}</p>
                          <p className="text-xs text-muted-foreground">
                            {activity.description} • {new Date(activity.date).toLocaleDateString()}
                          </p>
                        </div>
                        <span className={`text-sm font-medium ${
                          activity.points.startsWith('+') ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {activity.points}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2'} gap-4`}>
                <Card className="cursor-pointer transition-premium hover-lift" onClick={() => onNavigate('loyalty')}>
                  <CardContent className="p-4 text-center">
                    <Gift className="h-8 w-8 text-primary mx-auto mb-2" />
                    <h3 className="font-medium mb-1">Redeem Rewards</h3>
                    <p className="text-sm text-muted-foreground">Use your points for rewards</p>
                  </CardContent>
                </Card>
                
                <Card className="cursor-pointer transition-premium hover-lift">
                  <CardContent className="p-4 text-center">
                    <Users className="h-8 w-8 text-primary mx-auto mb-2" />
                    <h3 className="font-medium mb-1">Refer Friends</h3>
                    <p className="text-sm text-muted-foreground">Earn points for referrals</p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}