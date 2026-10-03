import React from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { Star, Coffee, Users, Leaf } from 'lucide-react';

interface HomeScreenProps {
  onNavigate: (screen: string, data?: any) => void;
}

export function HomeScreen({ onNavigate }: HomeScreenProps) {
  const featuredProducts = [
    {
      id: 1,
      name: 'Nyagatare Single Origin',
      price: 24.99,
      region: 'Eastern Province',
      roast: 'Medium',
      rating: 4.8,
      image: 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&h=300&fit=crop'
    },
    {
      id: 2,
      name: 'Musanze Mountain Blend',
      price: 22.99,
      region: 'Northern Province',
      roast: 'Dark',
      rating: 4.7,
      image: 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&h=300&fit=crop'
    }
  ];

  const farmerStories = [
    {
      id: 1,
      farmer: 'Marie Uwimana',
      story: 'Leading sustainable farming practices in Huye district',
      image: 'https://images.unsplash.com/photo-1594736797933-d0401ba4a3cb?w=400&h=300&fit=crop'
    },
    {
      id: 2,
      farmer: 'Jean Baptiste',
      story: 'Innovating coffee processing techniques in Nyamasheke',
      image: 'https://images.unsplash.com/photo-1571771019784-3ff35f4f4277?w=400&h=300&fit=crop'
    }
  ];

  return (
    <div className="pb-20 bg-background min-h-screen">
      {/* Header */}
      <div className="bg-primary text-primary-foreground p-6 rounded-b-2xl">
        <h1 className="text-2xl font-semibold mb-2">Welcome to Impactful Coffee</h1>
        <p className="opacity-90">Discover Rwanda's finest artisanal coffee</p>
      </div>

      {/* Stats Cards */}
      <div className="p-4 -mt-4">
        <div className="grid grid-cols-3 gap-3 mb-6">
          <Card className="text-center p-3">
            <CardContent className="p-0">
              <Coffee className="h-6 w-6 text-primary mx-auto mb-1" />
              <p className="text-sm">500+</p>
              <p className="text-xs text-muted-foreground">Farmers</p>
            </CardContent>
          </Card>
          <Card className="text-center p-3">
            <CardContent className="p-0">
              <Users className="h-6 w-6 text-accent mx-auto mb-1" />
              <p className="text-sm">15</p>
              <p className="text-xs text-muted-foreground">Cooperatives</p>
            </CardContent>
          </Card>
          <Card className="text-center p-3">
            <CardContent className="p-0">
              <Leaf className="h-6 w-6 text-accent mx-auto mb-1" />
              <p className="text-sm">100%</p>
              <p className="text-xs text-muted-foreground">Sustainable</p>
            </CardContent>
          </Card>
        </div>

        {/* Featured Products */}
        <div className="mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2>Featured Coffee</h2>
            <Button variant="ghost" size="sm" onClick={() => onNavigate('catalog')}>
              View All
            </Button>
          </div>
          <div className="space-y-4">
            {featuredProducts.map((product) => (
              <Card 
                key={product.id} 
                className="overflow-hidden cursor-pointer"
                onClick={() => onNavigate('product', product)}
              >
                <CardContent className="p-0">
                  <div className="flex">
                    <ImageWithFallback
                      src={product.image}
                      alt={product.name}
                      className="w-24 h-24 object-cover"
                    />
                    <div className="p-3 flex-1">
                      <h3 className="font-medium mb-1">{product.name}</h3>
                      <p className="text-sm text-muted-foreground mb-2">{product.region}</p>
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="secondary" className="text-xs">{product.roast}</Badge>
                        <div className="flex items-center gap-1">
                          <Star className="h-3 w-3 fill-current text-yellow-500" />
                          <span className="text-xs">{product.rating}</span>
                        </div>
                      </div>
                      <p className="text-primary font-medium">${product.price}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Farmer Stories */}
        <div className="mb-6">
          <h2 className="mb-4">Farmer Stories</h2>
          <div className="space-y-4">
            {farmerStories.map((story) => (
              <Card key={story.id} className="overflow-hidden">
                <CardContent className="p-0">
                  <ImageWithFallback
                    src={story.image}
                    alt={story.farmer}
                    className="w-full h-32 object-cover"
                  />
                  <div className="p-3">
                    <h3 className="font-medium mb-1">{story.farmer}</h3>
                    <p className="text-sm text-muted-foreground">{story.story}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Call to Action */}
        <Card className="bg-accent text-accent-foreground p-4 text-center">
          <CardContent className="p-0">
            <h3 className="font-medium mb-2">Join Our Coffee Community</h3>
            <p className="text-sm mb-3">Get exclusive access to new arrivals and farmer updates</p>
            <Button onClick={() => onNavigate('loyalty')} className="w-full">
              Learn About Rewards
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}