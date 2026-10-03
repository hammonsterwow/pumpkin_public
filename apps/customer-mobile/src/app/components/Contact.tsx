import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { MapPin, Phone, Mail, Clock, MessageCircle, Facebook, Instagram, Twitter } from 'lucide-react';

export function Contact() {
  const contactInfo = [
    {
      icon: MapPin,
      title: 'Visit Us',
      details: ['KG 7 Ave, Kigali', 'Rwanda, East Africa']
    },
    {
      icon: Phone,
      title: 'Call Us',
      details: ['+250 788 123 456', '+250 722 987 654']
    },
    {
      icon: Mail,
      title: 'Email Us',
      details: ['hello@impactfulcoffee.rw', 'support@impactfulcoffee.rw']
    },
    {
      icon: Clock,
      title: 'Business Hours',
      details: ['Mon-Fri: 8:00 AM - 6:00 PM', 'Sat: 9:00 AM - 4:00 PM']
    }
  ];

  const socialMedia = [
    { icon: Facebook, name: 'Facebook', handle: '@ImpactfulCoffeeRW' },
    { icon: Instagram, name: 'Instagram', handle: '@impactful_coffee' },
    { icon: Twitter, name: 'Twitter', handle: '@ImpactfulRW' }
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle form submission
    alert('Thank you for your message! We\'ll get back to you soon.');
  };

  return (
    <div className="pb-20 bg-background min-h-screen">
      {/* Header */}
      <div className="bg-primary text-primary-foreground p-6 rounded-b-2xl">
        <h1 className="text-2xl font-semibold mb-2">Get in Touch</h1>
        <p className="opacity-90">We'd love to hear from you</p>
      </div>

      <div className="p-4 space-y-6">
        {/* Contact Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5" />
              Send us a Message
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="firstName">First Name</Label>
                  <Input id="firstName" required />
                </div>
                <div>
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input id="lastName" required />
                </div>
              </div>
              <div>
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" required />
              </div>
              <div>
                <Label htmlFor="subject">Subject</Label>
                <Input id="subject" placeholder="How can we help you?" required />
              </div>
              <div>
                <Label htmlFor="message">Message</Label>
                <Textarea 
                  id="message" 
                  placeholder="Tell us more about your inquiry..."
                  rows={4}
                  required 
                />
              </div>
              <Button type="submit" className="w-full">
                Send Message
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Contact Information */}
        <div className="space-y-4">
          {contactInfo.map((info, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <info.icon className="h-5 w-5 text-primary mt-1" />
                  <div>
                    <h3 className="font-medium mb-1">{info.title}</h3>
                    {info.details.map((detail, idx) => (
                      <p key={idx} className="text-sm text-muted-foreground">{detail}</p>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Social Media */}
        <Card>
          <CardHeader>
            <CardTitle>Follow Us</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {socialMedia.map((social, index) => (
                <div key={index} className="flex items-center gap-3 p-2 rounded hover:bg-muted cursor-pointer">
                  <social.icon className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium text-sm">{social.name}</p>
                    <p className="text-xs text-muted-foreground">{social.handle}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* FAQ */}
        <Card>
          <CardHeader>
            <CardTitle>Frequently Asked Questions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-sm mb-1">How fresh is your coffee?</h3>
                <p className="text-xs text-muted-foreground">All our coffee is roasted within 2 weeks of shipping to ensure maximum freshness.</p>
              </div>
              <div>
                <h3 className="font-medium text-sm mb-1">Do you ship internationally?</h3>
                <p className="text-xs text-muted-foreground">Yes, we ship to most countries worldwide. Shipping costs vary by location.</p>
              </div>
              <div>
                <h3 className="font-medium text-sm mb-1">What makes Rwandan coffee special?</h3>
                <p className="text-xs text-muted-foreground">Rwanda's high altitude, volcanic soil, and ideal climate create unique flavor profiles with bright acidity and complex notes.</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Emergency Contact */}
        <Card className="bg-muted">
          <CardContent className="p-4 text-center">
            <h3 className="font-medium mb-2">Need Immediate Help?</h3>
            <p className="text-sm text-muted-foreground mb-3">
              For urgent order issues or customer support
            </p>
            <Button variant="outline" className="w-full">
              WhatsApp: +250 788 123 456
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}