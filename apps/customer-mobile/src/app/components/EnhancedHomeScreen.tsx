import React, { useState, useEffect } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { Star, Coffee, Users, Leaf, ArrowRight, Play, Award, Heart, ChevronLeft, ChevronRight } from 'lucide-react';

interface EnhancedHomeScreenProps {
  onNavigate: (screen: string, data?: any) => void;
  isMobile: boolean;
}

export function EnhancedHomeScreen({ onNavigate, isMobile }: EnhancedHomeScreenProps) {
  const [currentHero, setCurrentHero] = useState(0);
  const [currentFeatured, setCurrentFeatured] = useState(0);

  const heroSlides = [
    {
      id: 1,
      title: 'Experience Rwanda\'s Finest Coffee',
      subtitle: 'Handcrafted by skilled farmers in the Land of a Thousand Hills',
      image: 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=1200&h=600&fit=crop',
      cta: 'Discover Collection',
      badge: 'New Arrivals'
    },
    {
      id: 2,
      title: 'Limited Edition: Nyagatare Honey Process',
      subtitle: 'Exclusive seasonal blend with notes of honey, citrus, and chocolate',
      image: 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=1200&h=600&fit=crop',
      cta: 'Shop Limited Edition',
      badge: 'Limited Edition'
    },
    {
      id: 3,
      title: 'Empowering Communities',
      subtitle: 'Every cup supports 500+ coffee farmers and their families',
      image: 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=1200&h=600&fit=crop',
      cta: 'Learn Our Impact',
      badge: 'Social Impact'
    }
  ];

  const featuredProducts = [
    {
      id: 1,
      name: 'Nyagatare Single Origin',
      price: 24.99,
      originalPrice: 29.99,
      region: 'Eastern Province',
      roast: 'Medium',
      rating: 4.8,
      reviews: 124,
      image: 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&h=300&fit=crop',
      badges: ['Best Seller', 'Organic'],
      flavorNotes: ['Chocolate', 'Citrus', 'Caramel']
    },
    {
      id: 2,
      name: 'Musanze Mountain Blend',
      price: 22.99,
      region: 'Northern Province',
      roast: 'Dark',
      rating: 4.7,
      reviews: 89,
      image: 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&h=300&fit=crop',
      badges: ['Mountain Grown'],
      flavorNotes: ['Dark Chocolate', 'Smoky', 'Bold']
    },
    {
      id: 3,
      name: 'Kivu Lake Reserve',
      price: 28.99,
      region: 'Western Province',
      roast: 'Light',
      rating: 4.9,
      reviews: 156,
      image: 'https://images.unsplash.com/photo-1497636577773-f1231844b336?w=400&h=300&fit=crop',
      badges: ['Premium', 'Limited'],
      flavorNotes: ['Floral', 'Berry', 'Bright']
    },
    {
      id: 4,
      name: 'Huye Honey Process',
      price: 26.99,
      region: 'Southern Province',
      roast: 'Medium',
      rating: 4.6,
      reviews: 78,
      image: 'https://images.unsplash.com/photo-1511920170033-f8396924c348?w=400&h=300&fit=crop',
      badges: ['Honey Process'],
      flavorNotes: ['Honey', 'Stone Fruit', 'Sweet']
    }
  ];

  const impactStats = [
    { number: '500+', label: 'Farmers Supported', icon: Users },
    { number: '15', label: 'Cooperatives', icon: Coffee },
    { number: '100%', label: 'Sustainable', icon: Leaf },
    { number: '4.9★', label: 'Customer Rating', icon: Star }
  ];

  const testimonials = [
    {
      id: 1,
      name: 'Sarah Johnson',
      location: 'New York',
      rating: 5,
      text: 'The best coffee I\'ve ever tasted. You can really taste the passion and care in every cup.',
      image: 'https://images.unsplash.com/photo-1494790108755-2616b612b786?w=80&h=80&fit=crop&face'
    },
    {
      id: 2,
      name: 'David Chen',
      location: 'London',
      rating: 5,
      text: 'Knowing my coffee purchase supports Rwandan farmers makes it taste even better.',
      image: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=80&h=80&fit=crop&face'
    }
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentHero((prev) => (prev + 1) % heroSlides.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const nextFeatured = () => {
    setCurrentFeatured((prev) => (prev + 1) % Math.ceil(featuredProducts.length / (isMobile ? 1 : 3)));
  };

  const prevFeatured = () => {
    setCurrentFeatured((prev) => (prev - 1 + Math.ceil(featuredProducts.length / (isMobile ? 1 : 3))) % Math.ceil(featuredProducts.length / (isMobile ? 1 : 3)));
  };

  return (
    <div className={`bg-background min-h-screen ${isMobile ? 'pb-20' : ''}`}>
      {/* Hero Section */}
      <div className="relative h-[70vh] overflow-hidden">
        {heroSlides.map((slide, index) => (
          <div
            key={slide.id}
            className={`absolute inset-0 transition-all duration-1000 ease-in-out ${
              index === currentHero ? 'opacity-100 scale-100' : 'opacity-0 scale-105'
            }`}
          >
            <ImageWithFallback
              src={slide.image}
              alt={slide.title}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-black/60 via-black/30 to-transparent" />
            <div className="absolute inset-0 flex items-center">
              <div className={`${isMobile ? 'px-6' : 'max-w-7xl mx-auto px-6'} w-full`}>
                <div className="max-w-2xl text-white">
                  <Badge className="mb-4 bg-gold text-gold-foreground animate-fade-in">
                    {slide.badge}
                  </Badge>
                  <h1 className={`${isMobile ? 'text-3xl' : 'text-5xl'} font-bold mb-4 animate-slide-up`}>
                    {slide.title}
                  </h1>
                  <p className={`${isMobile ? 'text-lg' : 'text-xl'} mb-8 opacity-90 animate-slide-up`} style={{ animationDelay: '0.2s' }}>
                    {slide.subtitle}
                  </p>
                  <div className="flex gap-4 animate-slide-up" style={{ animationDelay: '0.4s' }}>
                    <Button 
                      size="lg" 
                      className="bg-primary hover:bg-primary/90 transition-premium hover-lift"
                      onClick={() => onNavigate('catalog')}
                    >
                      {slide.cta}
                      <ArrowRight className="ml-2 h-5 w-5" />
                    </Button>
                    <Button 
                      size="lg" 
                      variant="outline" 
                      className="border-white text-white hover:bg-white hover:text-primary transition-premium"
                      onClick={() => onNavigate('about')}
                    >
                      <Play className="mr-2 h-5 w-5" />
                      Watch Story
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
        
        {/* Hero Indicators */}
        <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 flex gap-2">
          {heroSlides.map((_, index) => (
            <button
              key={index}
              className={`w-3 h-3 rounded-full transition-premium ${
                index === currentHero ? 'bg-white' : 'bg-white/50'
              }`}
              onClick={() => setCurrentHero(index)}
            />
          ))}
        </div>
      </div>

      {/* Impact Stats */}
      <div className={`${isMobile ? 'px-4 py-8' : 'max-w-7xl mx-auto px-6 py-16'}`}>
        <div className={`grid ${isMobile ? 'grid-cols-2' : 'grid-cols-4'} gap-6`}>
          {impactStats.map((stat, index) => (
            <Card key={index} className="text-center transition-premium hover-lift animate-fade-in" style={{ animationDelay: `${index * 0.1}s` }}>
              <CardContent className="p-6">
                <stat.icon className="h-8 w-8 text-primary mx-auto mb-3" />
                <div className="text-3xl font-bold text-primary mb-2">{stat.number}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Featured Products Carousel */}
      <div className={`${isMobile ? 'px-4 py-8' : 'max-w-7xl mx-auto px-6 py-16'}`}>
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className={`${isMobile ? 'text-2xl' : 'text-3xl'} font-bold mb-2`}>Featured Coffee</h2>
            <p className="text-muted-foreground">Discover our most loved blends</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={prevFeatured}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={nextFeatured}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="overflow-hidden">
          <div 
            className={`flex transition-transform duration-500 ease-in-out gap-6`}
            style={{ 
              transform: `translateX(-${currentFeatured * (100 / (isMobile ? 1 : 3))}%)`,
              width: `${(featuredProducts.length / (isMobile ? 1 : 3)) * 100}%`
            }}
          >
            {featuredProducts.map((product) => (
              <Card 
                key={product.id} 
                className={`${isMobile ? 'w-full' : 'w-1/3'} flex-shrink-0 overflow-hidden cursor-pointer transition-premium hover-lift group`}
                onClick={() => onNavigate('product', product)}
              >
                <CardContent className="p-0">
                  <div className="relative overflow-hidden">
                    <ImageWithFallback
                      src={product.image}
                      alt={product.name}
                      className="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute top-3 left-3 flex flex-wrap gap-1">
                      {product.badges.map((badge, idx) => (
                        <Badge key={idx} className="bg-gold text-gold-foreground text-xs">
                          {badge}
                        </Badge>
                      ))}
                    </div>
                    {product.originalPrice && (
                      <div className="absolute top-3 right-3">
                        <Badge variant="destructive" className="text-xs">
                          Save ${(product.originalPrice - product.price).toFixed(2)}
                        </Badge>
                      </div>
                    )}
                    <Button
                      size="sm"
                      className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Heart className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold mb-2">{product.name}</h3>
                    <p className="text-sm text-muted-foreground mb-2">{product.region}</p>
                    
                    {/* Flavor Notes */}
                    <div className="flex flex-wrap gap-1 mb-3">
                      {product.flavorNotes.slice(0, 3).map((note, idx) => (
                        <Badge key={idx} variant="secondary" className="text-xs">
                          {note}
                        </Badge>
                      ))}
                    </div>

                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 fill-current text-gold" />
                        <span className="text-sm font-medium">{product.rating}</span>
                        <span className="text-xs text-muted-foreground">({product.reviews})</span>
                      </div>
                      <Badge variant="secondary" className="text-xs">{product.roast}</Badge>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-primary">${product.price}</span>
                        {product.originalPrice && (
                          <span className="text-sm text-muted-foreground line-through">
                            ${product.originalPrice}
                          </span>
                        )}
                      </div>
                      <Button size="sm" className="transition-premium">
                        Add to Cart
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* Testimonials */}
      <div className={`bg-muted ${isMobile ? 'px-4 py-8' : 'py-16'}`}>
        <div className={`${isMobile ? '' : 'max-w-7xl mx-auto px-6'}`}>
          <div className="text-center mb-12">
            <h2 className={`${isMobile ? 'text-2xl' : 'text-3xl'} font-bold mb-4`}>What Our Customers Say</h2>
            <p className="text-muted-foreground">Join thousands of coffee lovers worldwide</p>
          </div>
          
          <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2'} gap-8`}>
            {testimonials.map((testimonial) => (
              <Card key={testimonial.id} className="transition-premium hover-lift">
                <CardContent className="p-6">
                  <div className="flex gap-1 mb-4">
                    {[...Array(testimonial.rating)].map((_, i) => (
                      <Star key={i} className="h-4 w-4 fill-current text-gold" />
                    ))}
                  </div>
                  <p className="text-muted-foreground mb-4">"{testimonial.text}"</p>
                  <div className="flex items-center gap-3">
                    <ImageWithFallback
                      src={testimonial.image}
                      alt={testimonial.name}
                      className="w-10 h-10 rounded-full object-cover"
                    />
                    <div>
                      <div className="font-medium">{testimonial.name}</div>
                      <div className="text-sm text-muted-foreground">{testimonial.location}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* Newsletter CTA */}
      <div className={`${isMobile ? 'px-4 py-8' : 'max-w-7xl mx-auto px-6 py-16'}`}>
        <Card className="bg-primary text-primary-foreground overflow-hidden">
          <CardContent className="p-0">
            <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2'} items-center`}>
              <div className={`${isMobile ? 'p-6' : 'p-12'}`}>
                <Award className="h-12 w-12 mb-4" />
                <h2 className={`${isMobile ? 'text-xl' : 'text-2xl'} font-bold mb-4`}>
                  Join the Coffee Connoisseur Club
                </h2>
                <p className="opacity-90 mb-6">
                  Get exclusive access to limited editions, brewing tips, and stories from our partner farmers.
                </p>
                <div className="flex gap-2">
                  <input
                    type="email"
                    placeholder="Enter your email"
                    className="flex-1 px-4 py-2 rounded-lg bg-white text-primary focus:outline-none"
                  />
                  <Button variant="secondary" className="whitespace-nowrap">
                    Subscribe
                  </Button>
                </div>
              </div>
              {!isMobile && (
                <div className="relative h-full min-h-[300px]">
                  <ImageWithFallback
                    src="https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=600&h=400&fit=crop"
                    alt="Coffee plantation"
                    className="w-full h-full object-cover"
                  />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}