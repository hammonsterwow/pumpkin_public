import React, { useState } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from './ui/dropdown-menu';
import { Search, ShoppingCart, Menu, User, Globe, Star, Sun, Moon, LogOut, Package, Crown } from 'lucide-react';
import { ImageWithFallback } from './figma/ImageWithFallback';

interface HeaderProps {
  activeScreen: string;
  onNavigate: (screen: string, data?: any) => void;
  cartItemCount: number;
  isMobile: boolean;
  user?: any;
  onToggleDarkMode: () => void;
  isDarkMode: boolean;
}

export function Header({ 
  activeScreen, 
  onNavigate, 
  cartItemCount, 
  isMobile, 
  user, 
  onToggleDarkMode, 
  isDarkMode 
}: HeaderProps) {
  const [showMegaMenu, setShowMegaMenu] = useState(false);
  const [showSearch, setShowSearch] = useState(false);

  const handleLogout = () => {
    // Clear user session
    localStorage.removeItem('user');
    // Navigate to home
    onNavigate('home');
    // Reload page to reset state
    window.location.reload();
  };

  const megaMenuItems = [
    {
      category: 'Coffee Origins',
      items: [
        { name: 'Nyagatare', description: 'Eastern Province' },
        { name: 'Musanze', description: 'Northern Province' },
        { name: 'Kivu Lake', description: 'Western Province' },
        { name: 'Huye', description: 'Southern Province' }
      ]
    },
    {
      category: 'Roast Levels',
      items: [
        { name: 'Light Roast', description: 'Bright & Floral' },
        { name: 'Medium Roast', description: 'Balanced & Smooth' },
        { name: 'Dark Roast', description: 'Bold & Rich' }
      ]
    },
    {
      category: 'Special Collections',
      items: [
        { name: 'Limited Editions', description: 'Seasonal exclusive' },
        { name: 'Farmer Selections', description: 'Direct trade' },
        { name: 'Ceremonial Grade', description: 'Premium quality' }
      ]
    }
  ];

  if (isMobile) {
    return (
      <div className="sticky top-0 z-50 bg-card border-b border-border glass-effect transition-colors duration-300">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
              <span className="text-primary-foreground text-sm font-semibold">IC</span>
            </div>
            <span className="font-semibold text-lg">Impactful Coffee</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onToggleDarkMode}>
              {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowSearch(!showSearch)}>
              <Search className="h-5 w-5" />
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => onNavigate('cart')}
              className="relative"
            >
              <ShoppingCart className="h-5 w-5" />
              {cartItemCount > 0 && (
                <Badge className="absolute -top-2 -right-2 h-5 w-5 flex items-center justify-center p-0 text-xs bg-gold text-gold-foreground">
                  {cartItemCount > 9 ? '9+' : cartItemCount}
                </Badge>
              )}
            </Button>
            {user ? (
              <Button variant="ghost" size="sm" onClick={() => onNavigate('profile')}>
                <Avatar className="h-6 w-6">
                  <AvatarImage src={user.avatar} />
                  <AvatarFallback className="text-xs">
                    {user.name.split(' ').map((n: string) => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => onNavigate('auth')}>
                <User className="h-5 w-5" />
              </Button>
            )}
          </div>
        </div>
        
        {showSearch && (
          <div className="px-4 pb-4 animate-slide-up">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <input
                type="text"
                placeholder="Search coffee, origins, flavors..."
                className="w-full pl-10 pr-4 py-2 bg-input-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-premium"
                autoFocus
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="sticky top-0 z-50 bg-card border-b border-border glass-effect transition-colors duration-300">
      {/* Top bar */}
      <div className="border-b border-border/50">
        <div className="max-w-7xl mx-auto px-6 py-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">Free shipping worldwide on orders $50+</span>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <Star className="h-4 w-4 text-gold fill-current" />
                <span className="text-muted-foreground">4.9/5 from 2,500+ reviews</span>
              </div>
              <Button variant="ghost" size="sm" onClick={() => onNavigate('contact')}>
                Contact Support
              </Button>
              <Button variant="ghost" size="sm" onClick={onToggleDarkMode}>
                {isDarkMode ? (
                  <div className="flex items-center gap-1">
                    <Sun className="h-4 w-4" />
                    <span>Light</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <Moon className="h-4 w-4" />
                    <span>Dark</span>
                  </div>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main header */}
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div 
            className="flex items-center gap-3 cursor-pointer transition-premium hover:opacity-80"
            onClick={() => onNavigate('home')}
          >
            <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center">
              <span className="text-primary-foreground font-semibold">IC</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold">Impactful Coffee</h1>
              <p className="text-xs text-muted-foreground">Artisanal Rwandan Coffee</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="hidden lg:flex items-center gap-8">
            <Button 
              variant={activeScreen === 'home' ? 'default' : 'ghost'}
              onClick={() => onNavigate('home')}
              className="transition-premium"
            >
              Home
            </Button>
            <div 
              className="relative"
              onMouseEnter={() => setShowMegaMenu(true)}
              onMouseLeave={() => setShowMegaMenu(false)}
            >
              <Button 
                variant={activeScreen === 'catalog' ? 'default' : 'ghost'}
                onClick={() => onNavigate('catalog')}
                className="transition-premium"
              >
                Coffee
              </Button>
              
              {/* Mega Menu */}
              {showMegaMenu && (
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 w-[600px] bg-card border border-border rounded-xl shadow-xl animate-fade-in">
                  <div className="p-6">
                    <div className="grid grid-cols-3 gap-6">
                      {megaMenuItems.map((section, index) => (
                        <div key={index}>
                          <h3 className="font-semibold text-sm mb-3 text-primary">{section.category}</h3>
                          <div className="space-y-2">
                            {section.items.map((item, idx) => (
                              <button
                                key={idx}
                                className="block w-full text-left p-2 rounded-lg hover:bg-muted transition-premium"
                                onClick={() => {
                                  onNavigate('catalog', { filter: item.name });
                                  setShowMegaMenu(false);
                                }}
                              >
                                <div className="font-medium text-sm">{item.name}</div>
                                <div className="text-xs text-muted-foreground">{item.description}</div>
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-6 pt-4 border-t border-border">
                      <div className="flex items-center gap-4">
                        <ImageWithFallback
                          src="https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=100&h=80&fit=crop"
                          alt="Featured coffee"
                          className="w-16 h-12 rounded-lg object-cover"
                        />
                        <div>
                          <p className="font-medium text-sm">New: Nyagatare Honey Process</p>
                          <p className="text-xs text-muted-foreground">Limited edition seasonal blend</p>
                          <Badge className="mt-1 bg-gold text-gold-foreground">Featured</Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <Button 
              variant={activeScreen === 'about' ? 'default' : 'ghost'}
              onClick={() => onNavigate('about')}
              className="transition-premium"
            >
              Our Story
            </Button>
            <Button 
              variant={activeScreen === 'blog' ? 'default' : 'ghost'}
              onClick={() => onNavigate('blog')}
              className="transition-premium"
            >
              Blog
            </Button>
            <Button 
              variant={activeScreen === 'loyalty' ? 'default' : 'ghost'}
              onClick={() => onNavigate('loyalty')}
              className="transition-premium"
            >
              Rewards
            </Button>
          </nav>

          {/* Right side actions */}
          <div className="flex items-center gap-4">
            {/* Search */}
            <div className="relative hidden md:block">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <input
                type="text"
                placeholder="Search coffee..."
                className="w-64 pl-10 pr-4 py-2 bg-input-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-premium"
              />
            </div>

            {/* User Account */}
            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="flex items-center gap-2 transition-premium hover-lift">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={user.avatar} />
                      <AvatarFallback>
                        {user.name.split(' ').map((n: string) => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <div className="text-left">
                      <div className="text-sm font-medium">{user.name}</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-1">
                        <Crown className="h-3 w-3 text-gold" />
                        {user.tier} • {user.loyaltyPoints} pts
                      </div>
                    </div>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem onClick={() => onNavigate('profile')}>
                    <User className="mr-2 h-4 w-4" />
                    My Profile
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onNavigate('profile')}>
                    <Package className="mr-2 h-4 w-4" />
                    Order History
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onNavigate('loyalty')}>
                    <Crown className="mr-2 h-4 w-4" />
                    Loyalty Program
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout}>
                    <LogOut className="mr-2 h-4 w-4" />
                    Sign Out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="ghost" onClick={() => onNavigate('auth', { mode: 'signin' })}>
                  Sign In
                </Button>
                <Button onClick={() => onNavigate('auth', { mode: 'signup' })}>
                  Sign Up
                </Button>
              </div>
            )}

            {/* Cart */}
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => onNavigate('cart')}
              className="relative transition-premium hover-lift"
            >
              <ShoppingCart className="h-5 w-5" />
              {cartItemCount > 0 && (
                <Badge className="absolute -top-2 -right-2 h-5 w-5 flex items-center justify-center p-0 text-xs bg-gold text-gold-foreground">
                  {cartItemCount > 9 ? '9+' : cartItemCount}
                </Badge>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}