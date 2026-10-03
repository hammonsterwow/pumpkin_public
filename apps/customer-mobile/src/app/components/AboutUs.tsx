import React from 'react';
import { Card, CardContent } from './ui/card';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { Leaf, Users, Award, Heart, Coffee, Globe } from 'lucide-react';

export function AboutUs() {
  const values = [
    {
      icon: Leaf,
      title: 'Sustainability',
      description: 'Committed to environmental protection and sustainable farming practices'
    },
    {
      icon: Users,
      title: 'Community',
      description: 'Empowering local farmers and supporting their families'
    },
    {
      icon: Award,
      title: 'Quality',
      description: 'Premium coffee with exceptional taste and ethical sourcing'
    },
    {
      icon: Heart,
      title: 'Impact',
      description: 'Creating positive change in Rwandan coffee communities'
    }
  ];

  const stats = [
    { number: '500+', label: 'Farmers Supported' },
    { number: '15', label: 'Cooperatives' },
    { number: '10+', label: 'Years Experience' },
    { number: '100%', label: 'Fair Trade' }
  ];

  return (
    <div className="pb-20 bg-background min-h-screen">
      {/* Hero Section */}
      <div className="relative">
        <ImageWithFallback
          src="https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=800&h=400&fit=crop"
          alt="Rwandan coffee farmers"
          className="w-full h-48 object-cover"
        />
        <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
          <div className="text-center text-white">
            <h1 className="text-2xl font-semibold mb-2">Our Story</h1>
            <p className="opacity-90">Brewing change, one cup at a time</p>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* Mission Statement */}
        <Card>
          <CardContent className="p-6 text-center">
            <Coffee className="h-12 w-12 text-primary mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-3">Our Mission</h2>
            <p className="text-muted-foreground leading-relaxed">
              To connect coffee lovers worldwide with Rwanda's exceptional artisanal coffee while 
              empowering local farmers, promoting sustainable practices, and creating lasting 
              positive impact in rural communities.
            </p>
          </CardContent>
        </Card>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4">
          {stats.map((stat, index) => (
            <Card key={index} className="text-center">
              <CardContent className="p-4">
                <div className="text-2xl font-semibold text-primary mb-1">{stat.number}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Our Story */}
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-semibold mb-4">The Impactful Coffee Story</h2>
            <div className="space-y-4 text-sm leading-relaxed text-muted-foreground">
              <p>
                Founded in 2014, Impactful Coffee was born from a simple yet powerful vision: 
                to showcase Rwanda's incredible coffee while ensuring that the farmers who grow 
                it receive fair compensation for their exceptional work.
              </p>
              <p>
                After the 1994 genocide, Rwanda embarked on a remarkable journey of rebuilding 
                and reconciliation. Coffee became a symbol of hope and unity, bringing communities 
                together around a shared purpose. We recognized the potential of Rwandan coffee 
                to compete with the world's finest origins.
              </p>
              <p>
                Today, we work directly with over 500 smallholder farmers across 15 cooperatives, 
                providing training in sustainable agriculture, quality processing, and business 
                skills. Our commitment goes beyond just buying coffee – we invest in long-term 
                relationships that transform lives and communities.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Values */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Our Values</h2>
          <div className="space-y-4">
            {values.map((value, index) => (
              <Card key={index}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <value.icon className="h-6 w-6 text-primary mt-1" />
                    <div>
                      <h3 className="font-medium mb-1">{value.title}</h3>
                      <p className="text-sm text-muted-foreground">{value.description}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Impact Section */}
        <Card className="bg-accent text-accent-foreground">
          <CardContent className="p-6">
            <Globe className="h-8 w-8 mx-auto mb-3" />
            <h2 className="text-xl font-semibold mb-3 text-center">Global Impact</h2>
            <p className="text-sm text-center leading-relaxed">
              Every bag of Impactful Coffee sold contributes to education programs, 
              healthcare initiatives, and infrastructure development in rural Rwanda. 
              Together, we're building a more sustainable and equitable coffee industry.
            </p>
          </CardContent>
        </Card>

        {/* Recognition */}
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-semibold mb-4">Recognition & Certifications</h2>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-primary" />
                <span>Fair Trade Certified</span>
              </div>
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-primary" />
                <span>Organic Certification</span>
              </div>
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-primary" />
                <span>Rainforest Alliance Certified</span>
              </div>
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-primary" />
                <span>Women in Coffee Excellence Award 2023</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}