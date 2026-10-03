import React from 'react';
import { Home, Search, ShoppingCart, User, Heart } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';

interface BottomNavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  cartItemCount: number;
  user?: any;
}

export function BottomNavigation({ activeTab, onTabChange, cartItemCount, user }: BottomNavigationProps) {
  const tabs = [
    { id: 'home', icon: Home, label: 'Home' },
    { id: 'catalog', icon: Search, label: 'Browse' },
    { id: 'cart', icon: ShoppingCart, label: 'Cart' },
    { id: 'loyalty', icon: Heart, label: 'Rewards' },
    { id: 'profile', icon: User, label: user ? 'Profile' : 'Account' },
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-card border-t border-border z-50 transition-colors duration-300">
      <div className="flex justify-around items-center py-2">
        {tabs.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={`flex flex-col items-center p-2 relative transition-colors duration-200 ${
              activeTab === id ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            {id === 'profile' && user ? (
              <div className="relative">
                <Avatar className="h-5 w-5">
                  <AvatarImage src={user.avatar} />
                  <AvatarFallback className="text-xs">
                    {user.name.split(' ').map((n: string) => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                {user.loyaltyPoints > 0 && (
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-gold rounded-full flex items-center justify-center">
                    <span className="text-xs text-gold-foreground font-bold">!</span>
                  </div>
                )}
              </div>
            ) : (
              <Icon size={20} />
            )}
            <span className="text-xs mt-1">{label}</span>
            {id === 'cart' && cartItemCount > 0 && (
              <div className="absolute -top-1 -right-1 bg-primary text-primary-foreground rounded-full w-5 h-5 flex items-center justify-center text-xs">
                {cartItemCount > 9 ? '9+' : cartItemCount}
              </div>
            )}
            {id === 'loyalty' && user && user.loyaltyPoints > 0 && (
              <div className="absolute -top-1 -right-1 w-2 h-2 bg-gold rounded-full"></div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}