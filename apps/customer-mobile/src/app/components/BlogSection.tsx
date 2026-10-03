import React, { useState } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { Search, Calendar, User, Clock, Coffee, Leaf, Users, ChevronRight, Heart, MessageCircle, Share2 } from 'lucide-react';

interface BlogSectionProps {
  onNavigate: (screen: string, data?: any) => void;
  isMobile: boolean;
}

export function BlogSection({ onNavigate, isMobile }: BlogSectionProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const categories = [
    { id: 'all', name: 'All Posts', count: 24 },
    { id: 'brewing', name: 'Brewing Tips', count: 8 },
    { id: 'farmers', name: 'Farmer Stories', count: 6 },
    { id: 'sustainability', name: 'Sustainability', count: 5 },
    { id: 'culture', name: 'Coffee Culture', count: 5 }
  ];

  const featuredPost = {
    id: 1,
    title: 'The Complete Guide to Brewing Perfect Pour-Over Coffee',
    excerpt: 'Master the art of pour-over brewing with our comprehensive guide, featuring tips from world-class baristas and coffee experts.',
    content: 'Pour-over coffee brewing is both an art and a science. In this comprehensive guide, we\'ll walk you through every step...',
    category: 'brewing',
    author: 'Sarah Chen',
    authorRole: 'Head of Coffee Quality',
    publishDate: '2024-01-15',
    readTime: '8 min read',
    image: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=800&h=400&fit=crop',
    likes: 156,
    comments: 23,
    featured: true
  };

  const blogPosts = [
    {
      id: 2,
      title: 'Meet Marie: The Coffee Farmer Changing Lives in Huye',
      excerpt: 'Discover how Marie Uwimana is leading her cooperative to new heights and empowering women in coffee farming.',
      category: 'farmers',
      author: 'David Mugisha',
      authorRole: 'Impact Coordinator',
      publishDate: '2024-01-12',
      readTime: '6 min read',
      image: 'https://images.unsplash.com/photo-1594736797933-d0401ba4a3cb?w=400&h=250&fit=crop',
      likes: 89,
      comments: 12
    },
    {
      id: 3,
      title: '5 Sustainable Practices Every Coffee Lover Should Know',
      excerpt: 'Learn how your coffee choices can make a positive impact on the environment and farming communities.',
      category: 'sustainability',
      author: 'Emma Thompson',
      authorRole: 'Sustainability Manager',
      publishDate: '2024-01-10',
      readTime: '5 min read',
      image: 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=400&h=250&fit=crop',
      likes: 124,
      comments: 18
    },
    {
      id: 4,
      title: 'The History of Coffee in Rwanda: From Colonial Times to Today',
      excerpt: 'Explore the fascinating journey of coffee cultivation in Rwanda and its role in the country\'s development.',
      category: 'culture',
      author: 'Jean Baptiste',
      authorRole: 'Coffee Historian',
      publishDate: '2024-01-08',
      readTime: '10 min read',
      image: 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&h=250&fit=crop',
      likes: 67,
      comments: 9
    },
    {
      id: 5,
      title: 'Cold Brew vs. Iced Coffee: What\'s the Difference?',
      excerpt: 'Demystify the difference between cold brew and iced coffee, plus recipes for both.',
      category: 'brewing',
      author: 'Alex Rodriguez',
      authorRole: 'Senior Barista',
      publishDate: '2024-01-05',
      readTime: '4 min read',
      image: 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400&h=250&fit=crop',
      likes: 98,
      comments: 15
    },
    {
      id: 6,
      title: 'Building Schools with Coffee: Our Education Initiative',
      excerpt: 'See how coffee sales are funding education projects in rural Rwanda communities.',
      category: 'farmers',
      author: 'Grace Mukamana',
      authorRole: 'Community Relations',
      publishDate: '2024-01-03',
      readTime: '7 min read',
      image: 'https://images.unsplash.com/photo-1497486751825-1233686d5d80?w=400&h=250&fit=crop',
      likes: 145,
      comments: 28
    }
  ];

  const filteredPosts = blogPosts.filter(post => {
    const matchesSearch = post.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         post.excerpt.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || post.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'brewing': return Coffee;
      case 'farmers': return Users;
      case 'sustainability': return Leaf;
      case 'culture': return Coffee;
      default: return Coffee;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'brewing': return 'bg-primary text-primary-foreground';
      case 'farmers': return 'bg-accent text-accent-foreground';
      case 'sustainability': return 'bg-green-600 text-white';
      case 'culture': return 'bg-gold text-gold-foreground';
      default: return 'bg-muted text-muted-foreground';
    }
  };

  return (
    <div className={`bg-background min-h-screen ${isMobile ? 'pb-20' : ''}`}>
      {/* Header */}
      <div className="bg-primary text-primary-foreground">
        <div className={`${isMobile ? 'px-4 py-8' : 'max-w-7xl mx-auto px-6 py-16'}`}>
          <div className="text-center">
            <h1 className={`${isMobile ? 'text-2xl' : 'text-4xl'} font-bold mb-4`}>
              Coffee Stories & Culture
            </h1>
            <p className={`${isMobile ? 'text-base' : 'text-lg'} opacity-90 max-w-2xl mx-auto`}>
              Dive into the world of coffee with brewing tips, farmer stories, and insights into 
              sustainable coffee culture from Rwanda and beyond.
            </p>
          </div>
        </div>
      </div>

      <div className={`${isMobile ? 'px-4 py-6' : 'max-w-7xl mx-auto px-6 py-12'}`}>
        {/* Search and Categories */}
        <div className="mb-8">
          <div className="relative mb-6">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
            <Input
              placeholder="Search articles..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-12 py-3"
            />
          </div>

          <div className="flex gap-2 overflow-x-auto pb-2">
            {categories.map((category) => {
              const IconComponent = getCategoryIcon(category.id);
              return (
                <Button
                  key={category.id}
                  variant={selectedCategory === category.id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedCategory(category.id)}
                  className="whitespace-nowrap"
                >
                  <IconComponent className="h-4 w-4 mr-2" />
                  {category.name}
                  <Badge variant="secondary" className="ml-2 text-xs">
                    {category.count}
                  </Badge>
                </Button>
              );
            })}
          </div>
        </div>

        {/* Featured Post */}
        <Card className="mb-8 overflow-hidden transition-premium hover-lift">
          <CardContent className="p-0">
            <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2'} items-center`}>
              <div className="relative">
                <ImageWithFallback
                  src={featuredPost.image}
                  alt={featuredPost.title}
                  className={`w-full ${isMobile ? 'h-48' : 'h-80'} object-cover`}
                />
                <Badge className="absolute top-4 left-4 bg-gold text-gold-foreground">
                  Featured
                </Badge>
              </div>
              <div className={`${isMobile ? 'p-6' : 'p-8'}`}>
                <Badge className={`mb-3 ${getCategoryColor(featuredPost.category)}`}>
                  {featuredPost.category}
                </Badge>
                <h2 className={`${isMobile ? 'text-xl' : 'text-2xl'} font-bold mb-3`}>
                  {featuredPost.title}
                </h2>
                <p className="text-muted-foreground mb-4 leading-relaxed">
                  {featuredPost.excerpt}
                </p>
                <div className="flex items-center gap-4 mb-4 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <User className="h-4 w-4" />
                    <span>{featuredPost.author}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <span>{featuredPost.readTime}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <Button onClick={() => onNavigate('blog-post', featuredPost)}>
                    Read Article
                    <ChevronRight className="ml-2 h-4 w-4" />
                  </Button>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Heart className="h-4 w-4" />
                      <span>{featuredPost.likes}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <MessageCircle className="h-4 w-4" />
                      <span>{featuredPost.comments}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Blog Posts Grid */}
        <div className={`grid ${isMobile ? 'grid-cols-1' : 'md:grid-cols-2 lg:grid-cols-3'} gap-6`}>
          {filteredPosts.map((post) => {
            const IconComponent = getCategoryIcon(post.category);
            return (
              <Card 
                key={post.id} 
                className="overflow-hidden cursor-pointer transition-premium hover-lift group"
                onClick={() => onNavigate('blog-post', post)}
              >
                <CardContent className="p-0">
                  <div className="relative overflow-hidden">
                    <ImageWithFallback
                      src={post.image}
                      alt={post.title}
                      className="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <Badge className={`absolute top-3 left-3 ${getCategoryColor(post.category)}`}>
                      <IconComponent className="h-3 w-3 mr-1" />
                      {post.category}
                    </Badge>
                  </div>
                  <div className="p-6">
                    <h3 className="font-semibold mb-3 line-clamp-2 group-hover:text-primary transition-colors">
                      {post.title}
                    </h3>
                    <p className="text-muted-foreground text-sm mb-4 line-clamp-3">
                      {post.excerpt}
                    </p>
                    
                    <div className="flex items-center gap-3 mb-4 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        <span>{post.author}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>{post.readTime}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span>{new Date(post.publishDate).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" className="p-0 h-auto">
                        Read More
                        <ChevronRight className="ml-1 h-3 w-3" />
                      </Button>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <Heart className="h-3 w-3" />
                          <span>{post.likes}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <MessageCircle className="h-3 w-3" />
                          <span>{post.comments}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {filteredPosts.length === 0 && (
          <div className="text-center py-12">
            <Search className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-medium mb-2">No articles found</h3>
            <p className="text-muted-foreground mb-4">Try adjusting your search or category filter</p>
            <Button onClick={() => { setSearchTerm(''); setSelectedCategory('all'); }}>
              Clear filters
            </Button>
          </div>
        )}

        {/* Newsletter Signup */}
        <Card className="mt-12 bg-muted">
          <CardContent className="p-8 text-center">
            <h3 className="text-xl font-semibold mb-3">Stay Updated</h3>
            <p className="text-muted-foreground mb-6">
              Get the latest coffee tips, farmer stories, and sustainability insights delivered to your inbox.
            </p>
            <div className="flex gap-2 max-w-md mx-auto">
              <Input 
                placeholder="Enter your email" 
                className="flex-1"
              />
              <Button>Subscribe</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}