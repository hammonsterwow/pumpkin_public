import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Separator } from './ui/separator';
import { Checkbox } from './ui/checkbox';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { X, Mail, Lock, User, Eye, EyeOff, Coffee, Shield, CheckCircle } from 'lucide-react';

interface AuthScreenProps {
  mode: 'signin' | 'signup';
  onAuth: (user: any) => void;
  onClose: () => void;
  onSwitchMode: (mode: 'signin' | 'signup') => void;
  isMobile: boolean;
}

export function AuthScreen({ mode, onAuth, onClose, onSwitchMode, isMobile }: AuthScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [agreeToTerms, setAgreeToTerms] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [showVerification, setShowVerification] = useState(false);
  const [verificationCode, setVerificationCode] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    // Simulate API call
    setTimeout(() => {
      if (mode === 'signup') {
        // Simulate email verification requirement
        setShowVerification(true);
        setIsLoading(false);
        return;
      }

      // Simulate successful sign in
      const mockUser = {
        id: '1',
        name: mode === 'signup' ? `${firstName} ${lastName}` : 'John Doe',
        email: email,
        avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&face',
        loyaltyPoints: 350,
        tier: 'Silver',
        joinDate: '2023-06-15'
      };
      
      onAuth(mockUser);
      setIsLoading(false);
    }, 1500);
  };

  const handleSocialAuth = (provider: string) => {
    setIsLoading(true);
    
    // Simulate social authentication
    setTimeout(() => {
      const mockUser = {
        id: '1',
        name: 'John Doe',
        email: 'john@example.com',
        avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&face',
        loyaltyPoints: 350,
        tier: 'Silver',
        joinDate: '2023-06-15'
      };
      
      onAuth(mockUser);
      setIsLoading(false);
    }, 1000);
  };

  const handlePasswordReset = () => {
    setIsLoading(true);
    
    // Simulate password reset email
    setTimeout(() => {
      setIsLoading(false);
      setShowResetPassword(false);
      alert('Password reset link sent to your email!');
    }, 1000);
  };

  const handleVerification = () => {
    setIsLoading(true);
    
    // Simulate verification
    setTimeout(() => {
      const mockUser = {
        id: '1',
        name: `${firstName} ${lastName}`,
        email: email,
        avatar: undefined,
        loyaltyPoints: 0,
        tier: 'Bronze',
        joinDate: new Date().toISOString().split('T')[0]
      };
      
      onAuth(mockUser);
      setIsLoading(false);
    }, 1000);
  };

  if (showVerification) {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <Card className={`w-full ${isMobile ? 'max-w-sm' : 'max-w-md'} animate-scale-in`}>
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail className="h-8 w-8 text-primary" />
            </div>
            <CardTitle>Verify Your Email</CardTitle>
            <p className="text-muted-foreground text-sm">
              We've sent a verification code to {email}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="verification">Verification Code</Label>
              <Input
                id="verification"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value)}
                placeholder="Enter 6-digit code"
                maxLength={6}
                className="text-center text-lg tracking-widest"
              />
            </div>
            
            <Button 
              onClick={handleVerification}
              className="w-full" 
              disabled={isLoading || verificationCode.length !== 6}
            >
              {isLoading ? 'Verifying...' : 'Verify Email'}
            </Button>
            
            <div className="text-center">
              <button className="text-sm text-muted-foreground hover:text-primary transition-colors">
                Didn't receive code? Resend
              </button>
            </div>
            
            <Button variant="ghost" onClick={onClose} className="w-full">
              Cancel
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (showResetPassword) {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <Card className={`w-full ${isMobile ? 'max-w-sm' : 'max-w-md'} animate-scale-in`}>
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <Lock className="h-8 w-8 text-primary" />
            </div>
            <CardTitle>Reset Password</CardTitle>
            <p className="text-muted-foreground text-sm">
              Enter your email to receive a password reset link
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="resetEmail">Email Address</Label>
              <Input
                id="resetEmail"
                type="email"
                value={resetEmail}
                onChange={(e) => setResetEmail(e.target.value)}
                placeholder="your@email.com"
              />
            </div>
            
            <Button 
              onClick={handlePasswordReset}
              className="w-full" 
              disabled={isLoading || !resetEmail}
            >
              {isLoading ? 'Sending...' : 'Send Reset Link'}
            </Button>
            
            <Button 
              variant="ghost" 
              onClick={() => setShowResetPassword(false)} 
              className="w-full"
            >
              Back to Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-2'} ${isMobile ? 'w-full max-w-sm' : 'w-full max-w-4xl'} bg-card rounded-xl overflow-hidden shadow-2xl animate-scale-in`}>
        {/* Left Side - Branding (Hidden on mobile) */}
        {!isMobile && (
          <div className="bg-gradient-to-br from-primary to-primary/80 p-8 flex flex-col justify-center text-primary-foreground relative overflow-hidden">
            <div className="relative z-10">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-primary-foreground/20 rounded-full flex items-center justify-center">
                  <Coffee className="h-6 w-6" />
                </div>
                <span className="text-xl font-semibold">Impactful Coffee</span>
              </div>
              
              <h2 className="text-2xl font-bold mb-4">
                {mode === 'signup' ? 'Join Our Coffee Community' : 'Welcome Back'}
              </h2>
              
              <p className="opacity-90 mb-6">
                {mode === 'signup' 
                  ? 'Discover exceptional Rwandan coffee and support sustainable farming practices.'
                  : 'Sign in to access your personalized coffee experience and rewards.'
                }
              </p>
              
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5" />
                  <span>Premium artisanal coffee</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5" />
                  <span>Loyalty rewards program</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5" />
                  <span>Direct farmer support</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5" />
                  <span>Sustainable practices</span>
                </div>
              </div>
            </div>
            
            {/* Background Image */}
            <div className="absolute inset-0 opacity-10">
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=600&h=800&fit=crop"
                alt="Coffee"
                className="w-full h-full object-cover"
              />
            </div>
          </div>
        )}

        {/* Right Side - Form */}
        <div className="p-8 relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 hover:bg-muted rounded-full transition-colors"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="max-w-sm mx-auto">
            {/* Mobile Header */}
            {isMobile && (
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Coffee className="h-8 w-8 text-primary" />
                </div>
                <h2 className="text-xl font-semibold">Impactful Coffee</h2>
              </div>
            )}

            <div className="text-center mb-6">
              <h3 className="text-xl font-semibold mb-2">
                {mode === 'signup' ? 'Create Account' : 'Sign In'}
              </h3>
              <p className="text-muted-foreground text-sm">
                {mode === 'signup' 
                  ? 'Join our community of coffee lovers'
                  : 'Access your account and rewards'
                }
              </p>
            </div>

            {/* Social Sign In */}
            <div className="space-y-3 mb-6">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => handleSocialAuth('google')}
                disabled={isLoading}
              >
                <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </Button>
              
              <div className="grid grid-cols-2 gap-3">
                <Button
                  variant="outline"
                  onClick={() => handleSocialAuth('facebook')}
                  disabled={isLoading}
                >
                  <svg className="mr-2 h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                  Facebook
                </Button>
                
                <Button
                  variant="outline"
                  onClick={() => handleSocialAuth('apple')}
                  disabled={isLoading}
                >
                  <svg className="mr-2 h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12.017 0C6.624 0 2.246 4.377 2.246 9.771s4.378 9.771 9.771 9.771 9.771-4.377 9.771-9.771S17.41 0 12.017 0zm2.518 16.224c-1.188.894-2.717.894-3.905 0-.894-.67-1.341-1.565-1.341-2.683 0-1.117.447-2.012 1.341-2.682 1.188-.894 2.717-.894 3.905 0 .894.67 1.341 1.565 1.341 2.682 0 1.118-.447 2.013-1.341 2.683z"/>
                  </svg>
                  Apple
                </Button>
              </div>
            </div>

            <div className="flex items-center mb-6">
              <Separator className="flex-1" />
              <span className="px-3 text-muted-foreground text-sm">or</span>
              <Separator className="flex-1" />
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'signup' && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="firstName">First Name</Label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="firstName"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        placeholder="John"
                        className="pl-10"
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="lastName">Last Name</Label>
                    <Input
                      id="lastName"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Doe"
                      required
                    />
                  </div>
                </div>
              )}

              <div>
                <Label htmlFor="email">Email Address</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="pl-10 pr-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Eye className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                </div>
              </div>

              {mode === 'signup' && (
                <div>
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="confirmPassword"
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      className="pl-10 pr-10"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2"
                    >
                      {showConfirmPassword ? (
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Eye className="h-4 w-4 text-muted-foreground" />
                      )}
                    </button>
                  </div>
                </div>
              )}

              {mode === 'signup' && (
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="terms"
                    checked={agreeToTerms}
                    onCheckedChange={(checked) => setAgreeToTerms(checked as boolean)}
                  />
                  <Label htmlFor="terms" className="text-sm">
                    I agree to the{' '}
                    <button type="button" className="text-primary hover:underline">
                      Terms of Service
                    </button>{' '}
                    and{' '}
                    <button type="button" className="text-primary hover:underline">
                      Privacy Policy
                    </button>
                  </Label>
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={isLoading || (mode === 'signup' && (!agreeToTerms || password !== confirmPassword))}
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                    {mode === 'signup' ? 'Creating Account...' : 'Signing In...'}
                  </div>
                ) : (
                  mode === 'signup' ? 'Create Account' : 'Sign In'
                )}
              </Button>

              {mode === 'signin' && (
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setShowResetPassword(true)}
                    className="text-sm text-muted-foreground hover:text-primary transition-colors"
                  >
                    Forgot your password?
                  </button>
                </div>
              )}
            </form>

            <div className="text-center mt-6">
              <span className="text-sm text-muted-foreground">
                {mode === 'signup' ? 'Already have an account?' : "Don't have an account?"}
              </span>
              <button
                onClick={() => onSwitchMode(mode === 'signup' ? 'signin' : 'signup')}
                className="ml-1 text-sm text-primary hover:underline font-medium"
              >
                {mode === 'signup' ? 'Sign In' : 'Sign Up'}
              </button>
            </div>

            {/* Security Notice */}
            <div className="mt-6 p-3 bg-muted/50 rounded-lg">
              <div className="flex items-start gap-2">
                <Shield className="h-4 w-4 text-muted-foreground mt-0.5" />
                <p className="text-xs text-muted-foreground">
                  Your information is protected with industry-standard encryption and security measures.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}