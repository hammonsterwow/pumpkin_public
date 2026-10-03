import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import { 
  MapPin, Phone, Mail, ExternalLink, Package, 
  Instagram, Facebook, Twitter, Linkedin, Youtube,
  CreditCard, Smartphone, Globe, ChevronDown, Sun, Moon
} from 'lucide-react';

interface FooterProps {
  onNavigate: (screen: string, data?: any) => void;
  onToggleDarkMode: () => void;
  isDarkMode: boolean;
  isMobile: boolean;
}

export function Footer({ onNavigate, onToggleDarkMode, isDarkMode, isMobile }: FooterProps) {
  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [trackingInput, setTrackingInput] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('English');
  const [showLanguageDropdown, setShowLanguageDropdown] = useState(false);

  const handleNewsletterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newsletterEmail) {
      // Simulate newsletter subscription
      alert('Thank you for joining our Coffee Club! You\'ll receive exclusive updates and offers.');
      setNewsletterEmail('');
    }
  };

  const handleTrackOrder = () => {
    if (trackingInput) {
      // Simulate order tracking
      alert(`Tracking order: ${trackingInput}`);
      setTrackingInput('');
    }
  };

  const openGoogleMaps = () => {
    window.open('https://maps.google.com/?q=Kigali,Rwanda', '_blank');
  };

  const socialLinks = [
    { 
      icon: Instagram, 
      name: 'Instagram', 
      url: 'https://instagram.com/impactfulcoffee',
      hoverColor: 'hover:text-pink-500'
    },
    { 
      icon: Facebook, 
      name: 'Facebook', 
      url: 'https://facebook.com/impactfulcoffee',
      hoverColor: 'hover:text-blue-600'
    },
    { 
      icon: Twitter, 
      name: 'X (Twitter)', 
      url: 'https://twitter.com/impactfulcoffee',
      hoverColor: 'hover:text-gray-900 dark:hover:text-white'
    },
    { 
      icon: Linkedin, 
      name: 'LinkedIn', 
      url: 'https://linkedin.com/company/impactfulcoffee',
      hoverColor: 'hover:text-blue-700'
    },
    { 
      icon: Youtube, 
      name: 'YouTube', 
      url: 'https://youtube.com/@impactfulcoffee',
      hoverColor: 'hover:text-red-600'
    }
  ];

  const paymentMethods = [
    { name: 'Visa', icon: '💳' },
    { name: 'Mastercard', icon: '💳' },
    { name: 'American Express', icon: '💳' },
    { name: 'PayPal', icon: '🅿️' },
    { name: 'Stripe', icon: '💫' },
    { name: 'MTN Mobile Money', icon: '📱' },
    { name: 'Airtel Money', icon: '📱' },
    { name: 'Apple Pay', icon: '🍎' },
    { name: 'Google Pay', icon: '🔵' }
  ];

  const languages = [
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'rw', name: 'Kinyarwanda', flag: '🇷🇼' },
    { code: 'fr', name: 'Français', flag: '🇫🇷' },
    { code: 'sw', name: 'Kiswahili', flag: '🇰🇪' }
  ];

  const quickLinks = [
    { name: 'Home', action: () => onNavigate('home') },
    { name: 'Shop', action: () => onNavigate('catalog') },
    { name: 'About Us', action: () => onNavigate('about') },
    { name: 'Impact Stories', action: () => onNavigate('about') },
    { name: 'Blog', action: () => onNavigate('blog') },
    { name: 'FAQ', action: () => onNavigate('contact') }
  ];

  const supportLinks = [
    { name: 'Contact Us', action: () => onNavigate('contact') },
    { name: 'Shipping & Returns', action: () => onNavigate('contact') },
    { name: 'Order Tracking', action: () => onNavigate('profile') },
    { name: 'Privacy Policy', action: () => alert('Privacy Policy') },
    { name: 'Terms & Conditions', action: () => alert('Terms & Conditions') }
  ];

  if (isMobile) {
    return (
      <footer className="bg-card border-t border-border mt-8 transition-colors duration-300">
        <div className="px-4 py-8">
          {/* Mobile Accordion-style Footer */}
          <div className="space-y-6">
            {/* Brand Section */}
            <div className="text-center">
              <div className="flex items-center justify-center gap-3 mb-4">
                <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center">
                  <span className="text-primary-foreground font-semibold">IC</span>
                </div>
                <span className="font-semibold text-lg">Impactful Coffee</span>
              </div>
              <p className="text-muted-foreground text-sm leading-relaxed mb-4">
                Premium Rwandan coffee empowering farmers and supporting sustainable practices.
              </p>
              
              {/* Contact Info */}
              <div className="space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <MapPin className="h-4 w-4" />
                  <span>Kigali, Rwanda</span>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="p-0 h-auto"
                    onClick={openGoogleMaps}
                  >
                    <ExternalLink className="h-3 w-3" />
                  </Button>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <Phone className="h-4 w-4" />
                  <a href="tel:+250788123456" className="hover:text-primary transition-colors">
                    +250 788 123 456
                  </a>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <Mail className="h-4 w-4" />
                  <a href="mailto:hello@impactfulcoffee.rw" className="hover:text-primary transition-colors">
                    hello@impactfulcoffee.rw
                  </a>
                </div>
              </div>
            </div>

            {/* Newsletter Signup */}
            <div className="bg-muted/50 rounded-lg p-4">
              <h3 className="font-semibold mb-2 text-center">Join Our Coffee Club</h3>
              <p className="text-sm text-muted-foreground text-center mb-4">
                Get exclusive updates, brewing tips, and special offers
              </p>
              <form onSubmit={handleNewsletterSubmit} className="space-y-3">
                <Input
                  type="email"
                  placeholder="your@email.com"
                  value={newsletterEmail}
                  onChange={(e) => setNewsletterEmail(e.target.value)}
                  className="text-center"
                />
                <Button type="submit" className="w-full" disabled={!newsletterEmail}>
                  Subscribe
                </Button>
              </form>
            </div>

            {/* Order Tracking */}
            <div className="bg-muted/30 rounded-lg p-4">
              <h3 className="font-semibold mb-2 text-center">Track Your Order</h3>
              <div className="flex gap-2">
                <Input
                  placeholder="Order # or Email"
                  value={trackingInput}
                  onChange={(e) => setTrackingInput(e.target.value)}
                  className="flex-1"
                />
                <Button onClick={handleTrackOrder} disabled={!trackingInput}>
                  Track
                </Button>
              </div>
            </div>

            {/* Quick Links */}
            <div>
              <h3 className="font-semibold mb-3 text-center">Quick Links</h3>
              <div className="grid grid-cols-2 gap-2">
                {quickLinks.map((link, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    size="sm"
                    onClick={link.action}
                    className="justify-start text-muted-foreground hover:text-primary"
                  >
                    {link.name}
                  </Button>
                ))}
              </div>
            </div>

            {/* Customer Support */}
            <div>
              <h3 className="font-semibold mb-3 text-center">Customer Support</h3>
              <div className="space-y-1">
                {supportLinks.map((link, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    size="sm"
                    onClick={link.action}
                    className="w-full justify-center text-muted-foreground hover:text-primary"
                  >
                    {link.name}
                  </Button>
                ))}
              </div>
            </div>

            {/* Social Media */}
            <div>
              <h3 className="font-semibold mb-3 text-center">Follow Us</h3>
              <div className="flex justify-center gap-4">
                {socialLinks.map((social, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(social.url, '_blank')}
                    className={`p-2 transition-all duration-300 hover-lift ${social.hoverColor}`}
                  >
                    <social.icon className="h-5 w-5" />
                    <span className="sr-only">{social.name}</span>
                  </Button>
                ))}
              </div>
            </div>

            {/* Payment Methods */}
            <div>
              <h3 className="font-semibold mb-3 text-center">We Accept</h3>
              <div className="grid grid-cols-3 gap-2">
                {paymentMethods.slice(0, 9).map((payment, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-center gap-1 p-2 bg-muted/50 rounded text-xs"
                  >
                    <span>{payment.icon}</span>
                    <span className="truncate">{payment.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <Separator className="my-6" />
          <div className="space-y-4 text-center">
            <div className="flex items-center justify-center gap-4">
              <Button variant="ghost" size="sm" onClick={onToggleDarkMode}>
                {isDarkMode ? (
                  <div className="flex items-center gap-1">
                    <Sun className="h-4 w-4" />
                    <span className="text-xs">Light</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <Moon className="h-4 w-4" />
                    <span className="text-xs">Dark</span>
                  </div>
                )}
              </Button>
              
              <div className="relative">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowLanguageDropdown(!showLanguageDropdown)}
                  className="flex items-center gap-1"
                >
                  <Globe className="h-4 w-4" />
                  <span className="text-xs">🇺🇸 EN</span>
                  <ChevronDown className="h-3 w-3" />
                </Button>
                
                {showLanguageDropdown && (
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 bg-card border border-border rounded-lg shadow-lg z-10">
                    {languages.map((lang) => (
                      <button
                        key={lang.code}
                        className="w-full px-3 py-2 text-left hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg"
                        onClick={() => {
                          setSelectedLanguage(lang.name);
                          setShowLanguageDropdown(false);
                        }}
                      >
                        <span className="text-sm">{lang.flag} {lang.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="text-xs text-muted-foreground space-y-2">
              <p>&copy; 2025 Impactful Coffee. All Rights Reserved.</p>
              <p>Made with ❤️ in Rwanda</p>
              <Badge variant="outline" className="text-xs">
                Powered by Shopify
              </Badge>
            </div>
          </div>
        </div>
      </footer>
    );
  }

  return (
    <footer className="bg-card border-t border-border mt-16 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Main Footer Content */}
        <div className="grid grid-cols-12 gap-8">
          {/* Left Column - Brand & Contact */}
          <div className="col-span-12 lg:col-span-3">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center">
                <span className="text-primary-foreground font-semibold">IC</span>
              </div>
              <span className="font-semibold text-lg">Impactful Coffee</span>
            </div>
            
            <p className="text-muted-foreground text-sm leading-relaxed mb-6">
              Premium Rwandan coffee that empowers farmers and supports sustainable practices worldwide.
            </p>

            {/* Address & Contact */}
            <div className="space-y-3 mb-6">
              <div className="flex items-start gap-3 group">
                <MapPin className="h-4 w-4 text-muted-foreground mt-0.5 group-hover:text-primary transition-colors" />
                <div>
                  <p className="text-sm font-medium">Impactful Coffee HQ</p>
                  <p className="text-sm text-muted-foreground">KN 78 St, Kigali, Rwanda</p>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="p-0 h-auto text-xs text-primary hover:underline mt-1"
                    onClick={openGoogleMaps}
                  >
                    View on Google Maps <ExternalLink className="h-3 w-3 ml-1" />
                  </Button>
                </div>
              </div>

              <div className="flex items-center gap-3 group">
                <Phone className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                <a 
                  href="tel:+250788123456" 
                  className="text-sm hover:text-primary transition-colors"
                >
                  +250 788 123 456
                </a>
              </div>

              <div className="flex items-center gap-3 group">
                <Mail className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                <a 
                  href="mailto:hello@impactfulcoffee.rw" 
                  className="text-sm hover:text-primary transition-colors"
                >
                  hello@impactfulcoffee.rw
                </a>
              </div>
            </div>
          </div>

          {/* Middle Column 1 - Quick Links */}
          <div className="col-span-6 lg:col-span-2">
            <h3 className="font-semibold mb-4">Quick Links</h3>
            <div className="space-y-2">
              {quickLinks.map((link, index) => (
                <button
                  key={index}
                  onClick={link.action}
                  className="block text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  {link.name}
                </button>
              ))}
            </div>
          </div>

          {/* Middle Column 2 - Customer Support */}
          <div className="col-span-6 lg:col-span-2">
            <h3 className="font-semibold mb-4">Customer Support</h3>
            <div className="space-y-2">
              {supportLinks.map((link, index) => (
                <button
                  key={index}
                  onClick={link.action}
                  className="block text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  {link.name}
                </button>
              ))}
            </div>
          </div>

          {/* Middle Column 3 - Order Tracking */}
          <div className="col-span-12 lg:col-span-2">
            <h3 className="font-semibold mb-4">Track My Order</h3>
            <div className="space-y-3">
              <Input
                placeholder="Order # or Email"
                value={trackingInput}
                onChange={(e) => setTrackingInput(e.target.value)}
                className="text-sm"
              />
              <Button 
                onClick={handleTrackOrder} 
                size="sm" 
                className="w-full"
                disabled={!trackingInput}
              >
                <Package className="h-4 w-4 mr-2" />
                Track Order
              </Button>
            </div>
          </div>

          {/* Right Column - Social & Newsletter */}
          <div className="col-span-12 lg:col-span-3">
            {/* Social Media */}
            <div className="mb-6">
              <h3 className="font-semibold mb-4">Follow Our Journey</h3>
              <div className="flex gap-3">
                {socialLinks.map((social, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(social.url, '_blank')}
                    className={`p-2 transition-all duration-300 hover-lift ${social.hoverColor}`}
                  >
                    <social.icon className="h-5 w-5" />
                    <span className="sr-only">{social.name}</span>
                  </Button>
                ))}
              </div>
            </div>

            {/* Newsletter */}
            <div className="mb-6">
              <h3 className="font-semibold mb-2">Join Our Coffee Club</h3>
              <p className="text-xs text-muted-foreground mb-3">
                Get exclusive updates, brewing tips, and special offers
              </p>
              <form onSubmit={handleNewsletterSubmit} className="space-y-2">
                <Input
                  type="email"
                  placeholder="your@email.com"
                  value={newsletterEmail}
                  onChange={(e) => setNewsletterEmail(e.target.value)}
                  className="text-sm"
                />
                <Button 
                  type="submit" 
                  size="sm" 
                  className="w-full bg-gold text-gold-foreground hover:bg-gold/90"
                  disabled={!newsletterEmail}
                >
                  Subscribe
                </Button>
              </form>
            </div>

            {/* Payment Methods */}
            <div>
              <h3 className="font-semibold mb-3">We Accept</h3>
              <div className="grid grid-cols-3 gap-2">
                {paymentMethods.map((payment, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-center p-2 bg-muted/50 rounded text-xs hover:bg-muted transition-colors"
                    title={payment.name}
                  >
                    <span className="text-lg">{payment.icon}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Footer Bar */}
        <Separator className="my-8" />
        <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <p className="text-sm text-muted-foreground">
              &copy; 2025 Impactful Coffee. All Rights Reserved.
            </p>
            <span className="text-sm text-muted-foreground">Made with ❤️ in Rwanda</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Language Switcher */}
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowLanguageDropdown(!showLanguageDropdown)}
                className="flex items-center gap-2"
              >
                <Globe className="h-4 w-4" />
                <span className="text-sm">🇺🇸 English</span>
                <ChevronDown className="h-3 w-3" />
              </Button>
              
              {showLanguageDropdown && (
                <div className="absolute bottom-full right-0 mb-2 bg-card border border-border rounded-lg shadow-lg z-10 min-w-[160px]">
                  {languages.map((lang) => (
                    <button
                      key={lang.code}
                      className="w-full px-3 py-2 text-left hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg"
                      onClick={() => {
                        setSelectedLanguage(lang.name);
                        setShowLanguageDropdown(false);
                      }}
                    >
                      <span className="text-sm">{lang.flag} {lang.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Dark Mode Toggle */}
            <Button variant="ghost" size="sm" onClick={onToggleDarkMode}>
              {isDarkMode ? (
                <div className="flex items-center gap-2">
                  <Sun className="h-4 w-4" />
                  <span className="text-sm">Light Mode</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Moon className="h-4 w-4" />
                  <span className="text-sm">Dark Mode</span>
                </div>
              )}
            </Button>

            {/* Shopify Badge */}
            <Badge variant="outline" className="text-xs">
              Powered by Shopify
            </Badge>
          </div>
        </div>
      </div>
    </footer>
  );
}