import React, { useState } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { Search, Filter, Star } from 'lucide-react';

interface ProductCatalogProps {
  onNavigate: (screen: string, data?: any) => void;
}

export function ProductCatalog({ onNavigate }: ProductCatalogProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [coffeeTypeFilter, setCoffeeTypeFilter] = useState('all');
  const [roastFilter, setRoastFilter] = useState('all');
  const [regionFilter, setRegionFilter] = useState('all');

  const products = [
    {
      id: 1,
      name: 'Nyagatare Single Origin',
      price: 24.99,
      region: 'Eastern Province',
      roast: 'Medium',
      type: 'Arabica',
      rating: 4.8,
      reviews: 24,
      image: 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&h=300&fit=crop'
    },
    {
      id: 2,
      name: 'Musanze Mountain Blend',
      price: 22.99,
      region: 'Northern Province',
      roast: 'Dark',
      type: 'Arabica',
      rating: 4.7,
      reviews: 18,
      image: 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&h=300&fit=crop'
    },
    {
      id: 3,
      name: 'Kivu Lake Reserve',
      price: 28.99,
      region: 'Western Province',
      roast: 'Light',
      type: 'Arabica',
      rating: 4.9,
      reviews: 32,
      image: 'https://images.unsplash.com/photo-1497636577773-f1231844b336?w=400&h=300&fit=crop'
    },
    {
      id: 4,
      name: 'Huye Honey Process',
      price: 26.99,
      region: 'Southern Province',
      roast: 'Medium',
      type: 'Arabica',
      rating: 4.6,
      reviews: 15,
      image: 'https://images.unsplash.com/photo-1511920170033-f8396924c348?w=400&h=300&fit=crop'
    },
    {
      id: 5,
      name: 'Gicumbi Premium',
      price: 23.99,
      region: 'Northern Province',
      roast: 'Medium-Dark',
      type: 'Arabica',
      rating: 4.8,
      reviews: 27,
      image: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&h=300&fit=crop'
    },
    {
      id: 6,
      name: 'Nyamasheke Estate',
      price: 29.99,
      region: 'Western Province',
      roast: 'Dark',
      type: 'Arabica',
      rating: 4.7,
      reviews: 21,
      image: 'https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=400&h=300&fit=crop'
    }
  ];

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.region.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = coffeeTypeFilter === 'all' || product.type === coffeeTypeFilter;
    const matchesRoast = roastFilter === 'all' || product.roast === roastFilter;
    const matchesRegion = regionFilter === 'all' || product.region === regionFilter;
    
    return matchesSearch && matchesType && matchesRoast && matchesRegion;
  });

  return (
    <div className="pb-20 bg-background min-h-screen">
      {/* Header */}
      <div className="bg-card border-b border-border p-4">
        <h1 className="text-xl font-semibold mb-4">Browse Coffee</h1>
        
        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
          <Input
            placeholder="Search coffee or region..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Filters */}
        <div className="grid grid-cols-3 gap-2">
          <Select value={coffeeTypeFilter} onValueChange={setCoffeeTypeFilter}>
            <SelectTrigger className="text-xs">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="Arabica">Arabica</SelectItem>
              <SelectItem value="Robusta">Robusta</SelectItem>
            </SelectContent>
          </Select>

          <Select value={roastFilter} onValueChange={setRoastFilter}>
            <SelectTrigger className="text-xs">
              <SelectValue placeholder="Roast" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Roasts</SelectItem>
              <SelectItem value="Light">Light</SelectItem>
              <SelectItem value="Medium">Medium</SelectItem>
              <SelectItem value="Medium-Dark">Medium-Dark</SelectItem>
              <SelectItem value="Dark">Dark</SelectItem>
            </SelectContent>
          </Select>

          <Select value={regionFilter} onValueChange={setRegionFilter}>
            <SelectTrigger className="text-xs">
              <SelectValue placeholder="Region" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Regions</SelectItem>
              <SelectItem value="Eastern Province">Eastern</SelectItem>
              <SelectItem value="Western Province">Western</SelectItem>
              <SelectItem value="Northern Province">Northern</SelectItem>
              <SelectItem value="Southern Province">Southern</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Products Grid */}
      <div className="p-4">
        <div className="grid grid-cols-2 gap-4">
          {filteredProducts.map((product) => (
            <Card 
              key={product.id} 
              className="overflow-hidden cursor-pointer"
              onClick={() => onNavigate('product', product)}
            >
              <CardContent className="p-0">
                <ImageWithFallback
                  src={product.image}
                  alt={product.name}
                  className="w-full h-32 object-cover"
                />
                <div className="p-3">
                  <h3 className="font-medium mb-1 text-sm leading-tight">{product.name}</h3>
                  <p className="text-xs text-muted-foreground mb-2">{product.region}</p>
                  <div className="flex items-center gap-1 mb-2">
                    <Badge variant="secondary" className="text-xs">{product.roast}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-primary font-medium text-sm">${product.price}</p>
                    <div className="flex items-center gap-1">
                      <Star className="h-3 w-3 fill-current text-yellow-500" />
                      <span className="text-xs">{product.rating}</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {filteredProducts.length === 0 && (
          <div className="text-center py-8">
            <Filter className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-medium mb-2">No coffee found</h3>
            <p className="text-muted-foreground text-sm">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </div>
  );
}