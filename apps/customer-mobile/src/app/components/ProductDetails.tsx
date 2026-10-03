import React, { useState } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { ArrowLeft, Star, Plus, Minus, Heart, Coffee, Timer, Thermometer } from 'lucide-react';

interface ProductDetailsProps {
  product: any;
  onNavigate: (screen: string, data?: any) => void;
  onAddToCart: (product: any, quantity: number) => void;
}

export function ProductDetails({ product, onNavigate, onAddToCart }: ProductDetailsProps) {
  const [quantity, setQuantity] = useState(1);
  const [isFavorite, setIsFavorite] = useState(false);

  const reviews = [
    {
      id: 1,
      name: 'Sarah M.',
      rating: 5,
      comment: 'Absolutely amazing coffee! The flavor notes are exactly as described.',
      date: '2 days ago'
    },
    {
      id: 2,
      name: 'David K.',
      rating: 4,
      comment: 'Great quality, though I prefer a slightly darker roast.',
      date: '1 week ago'
    },
    {
      id: 3,
      name: 'Emma L.',
      rating: 5,
      comment: 'Love supporting Rwandan farmers. The coffee is exceptional.',
      date: '2 weeks ago'
    }
  ];

  const brewingTips = [
    {
      method: 'Pour Over',
      ratio: '1:16',
      temperature: '200°F',
      time: '3-4 min',
      grind: 'Medium-fine'
    },
    {
      method: 'French Press',
      ratio: '1:15',
      temperature: '200°F',
      time: '4 min',
      grind: 'Coarse'
    },
    {
      method: 'Espresso',
      ratio: '1:2',
      temperature: '203°F',
      time: '25-30 sec',
      grind: 'Fine'
    }
  ];

  const handleAddToCart = () => {
    onAddToCart(product, quantity);
    // Could show a toast notification here
  };

  return (
    <div className="pb-20 bg-background min-h-screen">
      {/* Header */}
      <div className="bg-card border-b border-border p-4 flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => onNavigate('catalog')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsFavorite(!isFavorite)}
        >
          <Heart className={`h-4 w-4 ${isFavorite ? 'fill-current text-red-500' : ''}`} />
        </Button>
      </div>

      {/* Product Image */}
      <div className="relative">
        <ImageWithFallback
          src={product.image}
          alt={product.name}
          className="w-full h-64 object-cover"
        />
        <div className="absolute top-4 right-4">
          <Badge variant="secondary">{product.roast}</Badge>
        </div>
      </div>

      {/* Product Info */}
      <div className="p-4">
        <div className="flex justify-between items-start mb-4">
          <div className="flex-1">
            <h1 className="text-xl font-semibold mb-2">{product.name}</h1>
            <p className="text-muted-foreground mb-2">{product.region} • {product.type}</p>
            <div className="flex items-center gap-2 mb-4">
              <div className="flex items-center gap-1">
                <Star className="h-4 w-4 fill-current text-yellow-500" />
                <span className="font-medium">{product.rating}</span>
                <span className="text-muted-foreground">({product.reviews} reviews)</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-semibold text-primary">${product.price}</p>
            <p className="text-sm text-muted-foreground">per 250g bag</p>
          </div>
        </div>

        {/* Quantity Selector */}
        <div className="flex items-center justify-between mb-6">
          <span className="font-medium">Quantity:</span>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setQuantity(Math.max(1, quantity - 1))}
              disabled={quantity <= 1}
            >
              <Minus className="h-4 w-4" />
            </Button>
            <span className="w-8 text-center">{quantity}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setQuantity(quantity + 1)}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Add to Cart */}
        <Button onClick={handleAddToCart} className="w-full mb-6" size="lg">
          Add to Cart • ${(product.price * quantity).toFixed(2)}
        </Button>

        {/* Tabs */}
        <Tabs defaultValue="description" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="description">Details</TabsTrigger>
            <TabsTrigger value="brewing">Brewing</TabsTrigger>
            <TabsTrigger value="reviews">Reviews</TabsTrigger>
          </TabsList>

          <TabsContent value="description" className="mt-4">
            <Card>
              <CardContent className="p-4">
                <p className="text-sm leading-relaxed mb-4">
                  This exceptional single-origin coffee comes from the {product.region} of Rwanda, 
                  where dedicated farmers employ sustainable growing practices at high altitudes. 
                  The unique terroir creates a distinctive flavor profile with notes of chocolate, 
                  citrus, and floral undertones.
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Origin:</span>
                    <span>{product.region}, Rwanda</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Variety:</span>
                    <span>{product.type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Process:</span>
                    <span>Washed</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Altitude:</span>
                    <span>1,800-2,100m</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Harvest:</span>
                    <span>March - July</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="brewing" className="mt-4">
            <div className="space-y-4">
              {brewingTips.map((tip, index) => (
                <Card key={index}>
                  <CardContent className="p-4">
                    <h3 className="font-medium mb-3 flex items-center gap-2">
                      <Coffee className="h-4 w-4 text-primary" />
                      {tip.method}
                    </h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Ratio:</span>
                        <span>{tip.ratio}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Thermometer className="h-3 w-3 text-muted-foreground" />
                        <span>{tip.temperature}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Timer className="h-3 w-3 text-muted-foreground" />
                        <span>{tip.time}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Grind:</span>
                        <span>{tip.grind}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="reviews" className="mt-4">
            <div className="space-y-4">
              {reviews.map((review) => (
                <Card key={review.id}>
                  <CardContent className="p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{review.name}</span>
                        <div className="flex">
                          {[...Array(5)].map((_, i) => (
                            <Star
                              key={i}
                              className={`h-3 w-3 ${i < review.rating ? 'fill-current text-yellow-500' : 'text-muted-foreground'}`}
                            />
                          ))}
                        </div>
                      </div>
                      <span className="text-xs text-muted-foreground">{review.date}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{review.comment}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}