import React, { useState } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { ArrowLeft, Star, Plus, Minus, Heart, Coffee, Timer, Thermometer, Play, RotateCcw, Award, Leaf, Users, ChevronLeft, ChevronRight, Share2, ShoppingCart } from 'lucide-react';

interface EnhancedProductDetailsProps {
  product: any;
  onNavigate: (screen: string, data?: any) => void;
  onAddToCart: (product: any, quantity: number) => void;
  isMobile: boolean;
}

export function EnhancedProductDetails({ product, onNavigate, onAddToCart, isMobile }: EnhancedProductDetailsProps) {
  const [quantity, setQuantity] = useState(1);
  const [isFavorite, setIsFavorite] = useState(false);
  const [selectedImage, setSelectedImage] = useState(0);
  const [showVideo, setShowVideo] = useState(false);
  const [selectedSize, setSelectedSize] = useState('250g');

  const productImages = [
    product.image,
    'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=600&h=600&fit=crop',
    'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&h=600&fit=crop',
    'https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=600&h=600&fit=crop'
  ];

  const sizes = [
    { weight: '250g', price: product.price, servings: '15-20 cups' },
    { weight: '500g', price: product.price * 1.8, servings: '30-40 cups' },
    { weight: '1kg', price: product.price * 3.2, servings: '60-80 cups' }
  ];

  const reviews = [
    {
      id: 1,
      name: 'Sarah M.',
      rating: 5,
      comment: 'Absolutely amazing coffee! The flavor notes are exactly as described. The chocolate and citrus blend perfectly.',
      date: '2 days ago',
      verified: true,
      helpful: 24
    },
    {
      id: 2,
      name: 'David K.',
      rating: 4,
      comment: 'Great quality, though I prefer a slightly darker roast. Still excellent value for the price.',
      date: '1 week ago',
      verified: true,
      helpful: 18
    },
    {
      id: 3,
      name: 'Emma L.',
      rating: 5,
      comment: 'Love supporting Rwandan farmers. The coffee is exceptional and the story behind it makes it even better.',
      date: '2 weeks ago',
      verified: true,
      helpful: 31
    }
  ];

  const brewingGuides = [
    {
      method: 'Pour Over (V60)',
      icon: Coffee,
      ratio: '1:16',
      temperature: '200°F (93°C)',
      time: '3-4 min',
      grind: 'Medium-fine',
      steps: [
        'Heat water to 200°F (93°C)',
        'Grind 22g coffee beans to medium-fine',
        'Place filter in V60 and rinse',
        'Add coffee and create small well',
        'Pour 50g water, bloom for 30s',
        'Continue pouring in circular motions',
        'Total brew time: 3-4 minutes'
      ]
    },
    {
      method: 'French Press',
      icon: Coffee,
      ratio: '1:15',
      temperature: '200°F (93°C)',
      time: '4 min',
      grind: 'Coarse',
      steps: [
        'Heat water to 200°F (93°C)',
        'Grind 30g coffee beans to coarse',
        'Add coffee to French press',
        'Pour hot water over coffee',
        'Stir gently and place lid',
        'Steep for 4 minutes',
        'Press down slowly and serve'
      ]
    },
    {
      method: 'Espresso',
      icon: Coffee,
      ratio: '1:2',
      temperature: '203°F (95°C)',
      time: '25-30 sec',
      grind: 'Fine',
      steps: [
        'Heat machine to 203°F (95°C)',
        'Grind 18g coffee beans to fine',
        'Distribute evenly in portafilter',
        'Tamp with 30lbs pressure',
        'Lock portafilter and start extraction',
        'Target 36g output in 25-30 seconds'
      ]
    }
  ];

  const relatedProducts = [
    {
      id: 7,
      name: 'Musanze Medium Roast',
      price: 23.99,
      image: 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=300&h=300&fit=crop',
      rating: 4.7
    },
    {
      id: 8,
      name: 'Kivu Dark Blend',
      price: 25.99,
      image: 'https://images.unsplash.com/photo-1497636577773-f1231844b336?w=300&h=300&fit=crop',
      rating: 4.8
    }
  ];

  const selectedSizeData = sizes.find(size => size.weight === selectedSize) || sizes[0];

  const handleAddToCart = () => {
    onAddToCart({ ...product, selectedSize, price: selectedSizeData.price }, quantity);
  };

  const nextImage = () => {
    setSelectedImage((prev) => (prev + 1) % productImages.length);
  };

  const prevImage = () => {
    setSelectedImage((prev) => (prev - 1 + productImages.length) % productImages.length);
  };

  return (
    <div className={`bg-background min-h-screen ${isMobile ? 'pb-20' : ''}`}>
      {/* Header */}
      <div className="bg-card border-b border-border sticky top-0 z-40">
        <div className={`${isMobile ? 'p-4' : 'max-w-7xl mx-auto px-6 py-4'} flex items-center justify-between`}>
          <Button variant="ghost" size="sm" onClick={() => onNavigate('catalog')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Catalog
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm">
              <Share2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsFavorite(!isFavorite)}
            >
              <Heart className={`h-4 w-4 ${isFavorite ? 'fill-current text-red-500' : ''}`} />
            </Button>
          </div>
        </div>
      </div>

      <div className={`${isMobile ? 'p-4' : 'max-w-7xl mx-auto px-6 py-8'}`}>
        <div className={`grid ${isMobile ? 'grid-cols-1' : 'lg:grid-cols-2'} gap-8`}>
          {/* Product Images */}
          <div className="space-y-4">
            {/* Main Image */}
            <div className="relative overflow-hidden rounded-lg bg-muted">
              <ImageWithFallback
                src={productImages[selectedImage]}
                alt={product.name}
                className="w-full h-96 object-cover"
              />
              <div className="absolute top-4 left-4 flex flex-wrap gap-2">
                {product.badges?.map((badge: string, idx: number) => (
                  <Badge key={idx} className="bg-gold text-gold-foreground">
                    {badge}
                  </Badge>
                ))}
              </div>
              
              {/* Navigation Arrows */}
              <Button
                variant="secondary"
                size="sm"
                className="absolute left-4 top-1/2 transform -translate-y-1/2 opacity-80 hover:opacity-100"
                onClick={prevImage}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="absolute right-4 top-1/2 transform -translate-y-1/2 opacity-80 hover:opacity-100"
                onClick={nextImage}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              {/* 360° View Button */}
              <Button
                variant="secondary"
                size="sm"
                className="absolute bottom-4 right-4"
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                360° View
              </Button>
            </div>

            {/* Thumbnail Images */}
            <div className="flex gap-2 overflow-x-auto">
              {productImages.map((image, index) => (
                <button
                  key={index}
                  className={`flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden border-2 transition-premium ${
                    selectedImage === index ? 'border-primary' : 'border-transparent'
                  }`}
                  onClick={() => setSelectedImage(index)}
                >
                  <ImageWithFallback
                    src={image}
                    alt={`${product.name} ${index + 1}`}
                    className="w-full h-full object-cover"
                  />
                </button>
              ))}
              
              {/* Video Thumbnail */}
              <button
                className="flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden border-2 border-transparent bg-muted flex items-center justify-center"
                onClick={() => setShowVideo(true)}
              >
                <Play className="h-6 w-6 text-primary" />
              </button>
            </div>
          </div>

          {/* Product Info */}
          <div className="space-y-6">
            {/* Basic Info */}
            <div>
              <h1 className={`${isMobile ? 'text-2xl' : 'text-3xl'} font-bold mb-2`}>{product.name}</h1>
              <p className="text-muted-foreground mb-4">{product.region} • {product.type} • {product.process} Process</p>
              
              <div className="flex items-center gap-4 mb-4">
                <div className="flex items-center gap-1">
                  <Star className="h-5 w-5 fill-current text-gold" />
                  <span className="font-medium">{product.rating}</span>
                  <span className="text-muted-foreground">({product.reviews} reviews)</span>
                </div>
                <Badge variant="secondary">{product.roast} Roast</Badge>
              </div>

              {/* Certifications */}
              <div className="flex flex-wrap gap-2 mb-6">
                {product.certifications?.map((cert: string, idx: number) => (
                  <div key={idx} className="flex items-center gap-1 px-2 py-1 bg-muted rounded-full">
                    {cert === 'Organic' && <Leaf className="h-3 w-3 text-accent" />}
                    {cert === 'Fair Trade' && <Award className="h-3 w-3 text-gold" />}
                    {cert === 'Direct Trade' && <Users className="h-3 w-3 text-primary" />}
                    <span className="text-xs font-medium">{cert}</span>
                  </div>
                ))}
              </div>

              <p className="text-muted-foreground leading-relaxed mb-6">
                {product.description || 'Experience the unique terroir of Rwanda with this exceptional single-origin coffee. Grown at high altitudes by skilled farmers using sustainable practices.'}
              </p>
            </div>

            {/* Flavor Profile */}
            <Card>
              <CardContent className="p-4">
                <h3 className="font-medium mb-3">Flavor Profile</h3>
                <div className="flex flex-wrap gap-2">
                  {product.flavorNotes?.map((note: string, idx: number) => (
                    <Badge key={idx} variant="secondary" className="text-sm">
                      {note}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Size Selection */}
            <div>
              <h3 className="font-medium mb-3">Choose Size</h3>
              <div className="grid grid-cols-3 gap-3">
                {sizes.map((size) => (
                  <button
                    key={size.weight}
                    className={`p-3 rounded-lg border-2 transition-premium text-center ${
                      selectedSize === size.weight 
                        ? 'border-primary bg-primary/5' 
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => setSelectedSize(size.weight)}
                  >
                    <div className="font-medium">{size.weight}</div>
                    <div className="text-sm text-muted-foreground">{size.servings}</div>
                    <div className="font-medium text-primary">${size.price}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Quantity & Add to Cart */}
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <span className="font-medium">Quantity:</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setQuantity(Math.max(1, quantity - 1))}
                    disabled={quantity <= 1}
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <span className="w-12 text-center font-medium">{quantity}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setQuantity(quantity + 1)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="flex gap-3">
                <Button 
                  onClick={handleAddToCart} 
                  className="flex-1 transition-premium hover-lift" 
                  size="lg"
                >
                  <ShoppingCart className="mr-2 h-5 w-5" />
                  Add to Cart • ${(selectedSizeData.price * quantity).toFixed(2)}
                </Button>
                <Button 
                  variant="outline" 
                  size="lg"
                  className="transition-premium"
                >
                  Buy Now
                </Button>
              </div>
            </div>

            {/* Product Details */}
            <Card>
              <CardContent className="p-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Origin:</span>
                    <span className="font-medium">{product.region}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Altitude:</span>
                    <span className="font-medium">{product.altitude || '1800-2100m'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Process:</span>
                    <span className="font-medium">{product.process || 'Washed'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Variety:</span>
                    <span className="font-medium">{product.type}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Tabs Section */}
        <div className="mt-12">
          <Tabs defaultValue="brewing" className="w-full">
            <TabsList className={`grid w-full ${isMobile ? 'grid-cols-2' : 'grid-cols-4'}`}>
              <TabsTrigger value="brewing">Brewing</TabsTrigger>
              <TabsTrigger value="reviews">Reviews</TabsTrigger>
              <TabsTrigger value="story">Our Story</TabsTrigger>
              <TabsTrigger value="related">Related</TabsTrigger>
            </TabsList>

            <TabsContent value="brewing" className="mt-6">
              <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-3'} gap-6`}>
                {brewingGuides.map((guide, index) => (
                  <Card key={index} className="transition-premium hover-lift">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <guide.icon className="h-6 w-6 text-primary" />
                        <h3 className="font-semibold">{guide.method}</h3>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Ratio:</span>
                          <span className="font-medium">{guide.ratio}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Thermometer className="h-3 w-3 text-muted-foreground" />
                          <span className="font-medium">{guide.temperature}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Timer className="h-3 w-3 text-muted-foreground" />
                          <span className="font-medium">{guide.time}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Grind:</span>
                          <span className="font-medium">{guide.grind}</span>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <h4 className="font-medium text-sm">Instructions:</h4>
                        <ol className="space-y-1 text-sm text-muted-foreground">
                          {guide.steps.map((step, stepIdx) => (
                            <li key={stepIdx} className="flex gap-2">
                              <span className="text-primary font-medium">{stepIdx + 1}.</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="reviews" className="mt-6">
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-semibold">Customer Reviews</h3>
                  <Button variant="outline">Write a Review</Button>
                </div>
                
                <div className="space-y-4">
                  {reviews.map((review) => (
                    <Card key={review.id} className="transition-premium hover-lift">
                      <CardContent className="p-6">
                        <div className="flex justify-between items-start mb-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
                              <span className="font-medium text-primary">{review.name[0]}</span>
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{review.name}</span>
                                {review.verified && (
                                  <Badge variant="secondary" className="text-xs">Verified</Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-1">
                                {[...Array(5)].map((_, i) => (
                                  <Star
                                    key={i}
                                    className={`h-3 w-3 ${i < review.rating ? 'fill-current text-gold' : 'text-muted-foreground'}`}
                                  />
                                ))}
                              </div>
                            </div>
                          </div>
                          <span className="text-xs text-muted-foreground">{review.date}</span>
                        </div>
                        
                        <p className="text-muted-foreground mb-3">{review.comment}</p>
                        
                        <div className="flex items-center gap-4 text-sm">
                          <button className="text-muted-foreground hover:text-primary transition-colors">
                            Helpful ({review.helpful})
                          </button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="story" className="mt-6">
              <Card>
                <CardContent className="p-6">
                  <div className="space-y-4">
                    <h3 className="text-xl font-semibold mb-4">The Story Behind This Coffee</h3>
                    <p className="text-muted-foreground leading-relaxed">
                      This exceptional coffee comes from a cooperative of 45 farmers in the {product.region} of Rwanda. 
                      Each family has been growing coffee for generations, passing down traditional knowledge while 
                      embracing modern sustainable practices.
                    </p>
                    <p className="text-muted-foreground leading-relaxed">
                      Through our direct trade partnership, we ensure that farmers receive fair compensation for their 
                      exceptional work. This not only improves their quality of life but also motivates them to continue 
                      producing some of the world's finest coffee.
                    </p>
                    <div className="grid grid-cols-2 gap-4 mt-6">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-primary">45</div>
                        <div className="text-sm text-muted-foreground">Partner Farmers</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-primary">$2.50</div>
                        <div className="text-sm text-muted-foreground">Premium per lb</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="related" className="mt-6">
              <div className="space-y-6">
                <h3 className="text-xl font-semibold">You Might Also Like</h3>
                <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2 lg:grid-cols-3'} gap-6`}>
                  {relatedProducts.map((relatedProduct) => (
                    <Card 
                      key={relatedProduct.id} 
                      className="cursor-pointer transition-premium hover-lift"
                      onClick={() => onNavigate('product', relatedProduct)}
                    >
                      <CardContent className="p-0">
                        <ImageWithFallback
                          src={relatedProduct.image}
                          alt={relatedProduct.name}
                          className="w-full h-48 object-cover rounded-t-lg"
                        />
                        <div className="p-4">
                          <h4 className="font-medium mb-2">{relatedProduct.name}</h4>
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-primary">${relatedProduct.price}</span>
                            <div className="flex items-center gap-1">
                              <Star className="h-3 w-3 fill-current text-gold" />
                              <span className="text-sm">{relatedProduct.rating}</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}