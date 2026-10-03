import React, { useState, useMemo } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Checkbox } from './ui/checkbox';
import { Slider } from './ui/slider';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { Search, Filter, Grid, List, Star, Heart, SlidersHorizontal, Award, Leaf, Coffee } from 'lucide-react';

interface AdvancedProductCatalogProps {
  onNavigate: (screen: string, data?: any) => void;
  isMobile: boolean;
}

export function AdvancedProductCatalog({ onNavigate, isMobile }: AdvancedProductCatalogProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(!isMobile);
  const [sortBy, setSortBy] = useState('popularity');
  
  // Filter states
  const [priceRange, setPriceRange] = useState([0, 50]);
  const [selectedRegions, setSelectedRegions] = useState<string[]>([]);
  const [selectedRoasts, setSelectedRoasts] = useState<string[]>([]);
  const [selectedFlavorNotes, setSelectedFlavorNotes] = useState<string[]>([]);
  const [selectedCertifications, setSelectedCertifications] = useState<string[]>([]);
  const [minRating, setMinRating] = useState(0);

  const products = [
    {
      id: 1,
      name: 'Nyagatare Single Origin',
      price: 24.99,
      originalPrice: 29.99,
      region: 'Eastern Province',
      roast: 'Medium',
      type: 'Arabica',
      rating: 4.8,
      reviews: 124,
      image: 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&h=300&fit=crop',
      badges: ['Best Seller', 'On Sale'],
      flavorNotes: ['Chocolate', 'Citrus', 'Caramel'],
      certifications: ['Organic', 'Fair Trade'],
      description: 'Rich and smooth with notes of dark chocolate and citrus',
      altitude: '1800-2100m',
      process: 'Washed',
      availability: 'In Stock'
    },
    {
      id: 2,
      name: 'Musanze Mountain Blend',
      price: 22.99,
      region: 'Northern Province',
      roast: 'Dark',
      type: 'Arabica',
      rating: 4.7,
      reviews: 89,
      image: 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&h=300&fit=crop',
      badges: ['Mountain Grown'],
      flavorNotes: ['Dark Chocolate', 'Smoky', 'Bold'],
      certifications: ['Rainforest Alliance'],
      description: 'Bold and smoky with intense chocolate notes',
      altitude: '2000-2300m',
      process: 'Natural',
      availability: 'In Stock'
    },
    {
      id: 3,
      name: 'Kivu Lake Reserve',
      price: 28.99,
      region: 'Western Province',
      roast: 'Light',
      type: 'Arabica',
      rating: 4.9,
      reviews: 156,
      image: 'https://images.unsplash.com/photo-1497636577773-f1231844b336?w=400&h=300&fit=crop',
      badges: ['Premium', 'Limited Edition'],
      flavorNotes: ['Floral', 'Berry', 'Bright'],
      certifications: ['Organic', 'Fair Trade', 'Bird Friendly'],
      description: 'Bright and floral with complex berry undertones',
      altitude: '1900-2200m',
      process: 'Honey',
      availability: 'Limited Stock'
    },
    {
      id: 4,
      name: 'Huye Honey Process',
      price: 26.99,
      region: 'Southern Province',
      roast: 'Medium',
      type: 'Arabica',
      rating: 4.6,
      reviews: 78,
      image: 'https://images.unsplash.com/photo-1511920170033-f8396924c348?w=400&h=300&fit=crop',
      badges: ['Honey Process'],
      flavorNotes: ['Honey', 'Stone Fruit', 'Sweet'],
      certifications: ['Organic'],
      description: 'Sweet and complex with honey and stone fruit notes',
      altitude: '1700-2000m',
      process: 'Honey',
      availability: 'In Stock'
    },
    {
      id: 5,
      name: 'Gicumbi Premium',
      price: 31.99,
      region: 'Northern Province',
      roast: 'Medium-Dark',
      type: 'Arabica',
      rating: 4.8,
      reviews: 92,
      image: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&h=300&fit=crop',
      badges: ['Premium'],
      flavorNotes: ['Nutty', 'Caramel', 'Full Body'],
      certifications: ['Fair Trade', 'Rainforest Alliance'],
      description: 'Full-bodied with rich nutty and caramel flavors',
      altitude: '1800-2100m',
      process: 'Semi-Washed',
      availability: 'In Stock'
    },
    {
      id: 6,
      name: 'Nyamasheke Estate',
      price: 33.99,
      region: 'Western Province',
      roast: 'Dark',
      type: 'Arabica',
      rating: 4.7,
      reviews: 67,
      image: 'https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=400&h=300&fit=crop',
      badges: ['Estate Grown'],
      flavorNotes: ['Spice', 'Dark Chocolate', 'Robust'],
      certifications: ['Organic', 'Direct Trade'],
      description: 'Robust and spicy with intense dark chocolate notes',
      altitude: '1900-2200m',
      process: 'Natural',
      availability: 'In Stock'
    }
  ];

  const filterOptions = {
    regions: ['Eastern Province', 'Western Province', 'Northern Province', 'Southern Province'],
    roasts: ['Light', 'Medium', 'Medium-Dark', 'Dark'],
    flavorNotes: ['Chocolate', 'Citrus', 'Berry', 'Floral', 'Nutty', 'Honey', 'Spice', 'Smoky'],
    certifications: ['Organic', 'Fair Trade', 'Rainforest Alliance', 'Bird Friendly', 'Direct Trade']
  };

  const filteredProducts = useMemo(() => {
    let filtered = products.filter(product => {
      const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           product.region.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           product.flavorNotes.some(note => note.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const matchesPrice = product.price >= priceRange[0] && product.price <= priceRange[1];
      const matchesRegion = selectedRegions.length === 0 || selectedRegions.includes(product.region);
      const matchesRoast = selectedRoasts.length === 0 || selectedRoasts.includes(product.roast);
      const matchesFlavorNotes = selectedFlavorNotes.length === 0 || 
                                selectedFlavorNotes.some(note => product.flavorNotes.includes(note));
      const matchesCertifications = selectedCertifications.length === 0 ||
                                   selectedCertifications.some(cert => product.certifications.includes(cert));
      const matchesRating = product.rating >= minRating;

      return matchesSearch && matchesPrice && matchesRegion && matchesRoast && 
             matchesFlavorNotes && matchesCertifications && matchesRating;
    });

    // Sort products
    switch (sortBy) {
      case 'price-low':
        filtered.sort((a, b) => a.price - b.price);
        break;
      case 'price-high':
        filtered.sort((a, b) => b.price - a.price);
        break;
      case 'rating':
        filtered.sort((a, b) => b.rating - a.rating);
        break;
      case 'newest':
        filtered.sort((a, b) => b.id - a.id);
        break;
      case 'name':
        filtered.sort((a, b) => a.name.localeCompare(b.name));
        break;
      default: // popularity
        filtered.sort((a, b) => b.reviews - a.reviews);
    }

    return filtered;
  }, [searchTerm, priceRange, selectedRegions, selectedRoasts, selectedFlavorNotes, selectedCertifications, minRating, sortBy]);

  const toggleFilter = (filterArray: string[], setFilter: React.Dispatch<React.SetStateAction<string[]>>, value: string) => {
    if (filterArray.includes(value)) {
      setFilter(filterArray.filter(item => item !== value));
    } else {
      setFilter([...filterArray, value]);
    }
  };

  const clearAllFilters = () => {
    setPriceRange([0, 50]);
    setSelectedRegions([]);
    setSelectedRoasts([]);
    setSelectedFlavorNotes([]);
    setSelectedCertifications([]);
    setMinRating(0);
    setSearchTerm('');
  };

  const ProductCard = ({ product }: { product: any }) => (
    <Card 
      className="overflow-hidden cursor-pointer transition-premium hover-lift group animate-fade-in"
      onClick={() => onNavigate('product', product)}
    >
      <CardContent className="p-0">
        <div className="relative overflow-hidden">
          <ImageWithFallback
            src={product.image}
            alt={product.name}
            className={`w-full ${viewMode === 'grid' ? 'h-48' : 'h-32'} object-cover group-hover:scale-105 transition-transform duration-500`}
          />
          <div className="absolute top-3 left-3 flex flex-wrap gap-1">
            {product.badges.map((badge: string, idx: number) => (
              <Badge key={idx} className="bg-gold text-gold-foreground text-xs">
                {badge}
              </Badge>
            ))}
          </div>
          <Button
            size="sm"
            variant="secondary"
            className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Heart className="h-4 w-4" />
          </Button>
          {product.availability === 'Limited Stock' && (
            <div className="absolute bottom-3 left-3">
              <Badge variant="destructive" className="text-xs">
                Limited Stock
              </Badge>
            </div>
          )}
        </div>
        
        <div className="p-4">
          {viewMode === 'list' && (
            <div className="flex gap-4">
              <div className="flex-1">
                <h3 className="font-semibold mb-1">{product.name}</h3>
                <p className="text-sm text-muted-foreground mb-2">{product.region} • {product.process} Process</p>
                <p className="text-sm text-muted-foreground mb-3">{product.description}</p>
              </div>
              <div className="text-right">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg font-bold text-primary">${product.price}</span>
                  {product.originalPrice && (
                    <span className="text-sm text-muted-foreground line-through">
                      ${product.originalPrice}
                    </span>
                  )}
                </div>
                <Button size="sm" className="w-full">Add to Cart</Button>
              </div>
            </div>
          )}
          
          {viewMode === 'grid' && (
            <>
              <h3 className="font-semibold mb-1">{product.name}</h3>
              <p className="text-sm text-muted-foreground mb-2">{product.region}</p>
              
              {/* Certifications */}
              <div className="flex flex-wrap gap-1 mb-2">
                {product.certifications.slice(0, 2).map((cert: string, idx: number) => (
                  <div key={idx} className="flex items-center gap-1">
                    {cert === 'Organic' && <Leaf className="h-3 w-3 text-accent" />}
                    {cert === 'Fair Trade' && <Award className="h-3 w-3 text-gold" />}
                    <span className="text-xs text-muted-foreground">{cert}</span>
                  </div>
                ))}
              </div>

              {/* Flavor Notes */}
              <div className="flex flex-wrap gap-1 mb-3">
                {product.flavorNotes.slice(0, 3).map((note: string, idx: number) => (
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
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className={`bg-background min-h-screen ${isMobile ? 'pb-20' : ''}`}>
      {/* Header */}
      <div className="bg-card border-b border-border">
        <div className={`${isMobile ? 'p-4' : 'max-w-7xl mx-auto px-6 py-6'}`}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className={`${isMobile ? 'text-xl' : 'text-2xl'} font-bold`}>Premium Coffee Collection</h1>
              <p className="text-muted-foreground">Discover Rwanda's finest artisanal coffee</p>
            </div>
            {!isMobile && (
              <div className="flex items-center gap-2">
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode('grid')}
                >
                  <Grid className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode('list')}
                >
                  <List className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
          
          {/* Search and Sort */}
          <div className="flex gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <Input
                placeholder="Search coffee, regions, flavors..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="popularity">Most Popular</SelectItem>
                <SelectItem value="rating">Highest Rated</SelectItem>
                <SelectItem value="price-low">Price: Low to High</SelectItem>
                <SelectItem value="price-high">Price: High to Low</SelectItem>
                <SelectItem value="newest">Newest</SelectItem>
                <SelectItem value="name">Name A-Z</SelectItem>
              </SelectContent>
            </Select>
            {isMobile && (
              <Button
                variant="outline"
                onClick={() => setShowFilters(!showFilters)}
              >
                <SlidersHorizontal className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Active Filters */}
          {(selectedRegions.length > 0 || selectedRoasts.length > 0 || selectedFlavorNotes.length > 0 || selectedCertifications.length > 0 || minRating > 0) && (
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="text-sm text-muted-foreground">Active filters:</span>
              {[...selectedRegions, ...selectedRoasts, ...selectedFlavorNotes, ...selectedCertifications].map((filter, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {filter}
                </Badge>
              ))}
              {minRating > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {minRating}+ stars
                </Badge>
              )}
              <Button variant="ghost" size="sm" onClick={clearAllFilters} className="text-xs h-6">
                Clear all
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className={`${isMobile ? 'p-4' : 'max-w-7xl mx-auto px-6 py-6'} flex gap-6`}>
        {/* Filters Sidebar */}
        {showFilters && (
          <div className={`${isMobile ? 'fixed inset-0 bg-background z-50 p-4' : 'w-80 flex-shrink-0'}`}>
            {isMobile && (
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">Filters</h2>
                <Button variant="ghost" onClick={() => setShowFilters(false)}>✕</Button>
              </div>
            )}
            
            <div className="space-y-6">
              {/* Price Range */}
              <div>
                <h3 className="font-medium mb-3">Price Range</h3>
                <Slider
                  value={priceRange}
                  onValueChange={setPriceRange}
                  max={50}
                  step={1}
                  className="mb-2"
                />
                <div className="flex justify-between text-sm text-muted-foreground">
                  <span>${priceRange[0]}</span>
                  <span>${priceRange[1]}</span>
                </div>
              </div>

              {/* Rating */}
              <div>
                <h3 className="font-medium mb-3">Minimum Rating</h3>
                <div className="space-y-2">
                  {[4, 3, 2, 1].map((rating) => (
                    <div key={rating} className="flex items-center space-x-2">
                      <Checkbox
                        checked={minRating === rating}
                        onCheckedChange={() => setMinRating(minRating === rating ? 0 : rating)}
                      />
                      <div className="flex items-center gap-1">
                        {[...Array(rating)].map((_, i) => (
                          <Star key={i} className="h-3 w-3 fill-current text-gold" />
                        ))}
                        <span className="text-sm">& up</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Regions */}
              <div>
                <h3 className="font-medium mb-3">Coffee Origin</h3>
                <div className="space-y-2">
                  {filterOptions.regions.map((region) => (
                    <div key={region} className="flex items-center space-x-2">
                      <Checkbox
                        checked={selectedRegions.includes(region)}
                        onCheckedChange={() => toggleFilter(selectedRegions, setSelectedRegions, region)}
                      />
                      <span className="text-sm">{region}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Roast Levels */}
              <div>
                <h3 className="font-medium mb-3">Roast Level</h3>
                <div className="space-y-2">
                  {filterOptions.roasts.map((roast) => (
                    <div key={roast} className="flex items-center space-x-2">
                      <Checkbox
                        checked={selectedRoasts.includes(roast)}
                        onCheckedChange={() => toggleFilter(selectedRoasts, setSelectedRoasts, roast)}
                      />
                      <span className="text-sm">{roast}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Flavor Notes */}
              <div>
                <h3 className="font-medium mb-3">Flavor Notes</h3>
                <div className="space-y-2">
                  {filterOptions.flavorNotes.map((note) => (
                    <div key={note} className="flex items-center space-x-2">
                      <Checkbox
                        checked={selectedFlavorNotes.includes(note)}
                        onCheckedChange={() => toggleFilter(selectedFlavorNotes, setSelectedFlavorNotes, note)}
                      />
                      <span className="text-sm">{note}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Certifications */}
              <div>
                <h3 className="font-medium mb-3">Certifications</h3>
                <div className="space-y-2">
                  {filterOptions.certifications.map((cert) => (
                    <div key={cert} className="flex items-center space-x-2">
                      <Checkbox
                        checked={selectedCertifications.includes(cert)}
                        onCheckedChange={() => toggleFilter(selectedCertifications, setSelectedCertifications, cert)}
                      />
                      <span className="text-sm">{cert}</span>
                    </div>
                  ))}
                </div>
              </div>

              {isMobile && (
                <div className="flex gap-2 pt-4">
                  <Button onClick={clearAllFilters} variant="outline" className="flex-1">
                    Clear All
                  </Button>
                  <Button onClick={() => setShowFilters(false)} className="flex-1">
                    Apply Filters
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Products Grid */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-6">
            <p className="text-muted-foreground">
              Showing {filteredProducts.length} of {products.length} products
            </p>
          </div>

          {filteredProducts.length === 0 ? (
            <div className="text-center py-12">
              <Coffee className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-medium mb-2">No coffee found</h3>
              <p className="text-muted-foreground mb-4">Try adjusting your search or filters</p>
              <Button onClick={clearAllFilters}>Clear all filters</Button>
            </div>
          ) : (
            <div className={`grid gap-6 ${
              viewMode === 'grid' 
                ? isMobile ? 'grid-cols-1' : 'grid-cols-2 lg:grid-cols-3'
                : 'grid-cols-1'
            }`}>
              {filteredProducts.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}