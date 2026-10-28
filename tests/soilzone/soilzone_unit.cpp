// Unit tests of the soil-zone interface functions (src/GWSoilZone.cpp), plan §9.1 G1-G6 plus randomized checks.
// build: g++ -std=c++11 -O2 -I$RAVEN_SRC/src soilzone_unit.cpp $RAVEN_SRC/src/GWSoilZone.cpp -o soilzone_unit
#include "GWSoilZone.h"
#include <cstdio>
#include <cmath>
#include <cstdlib>
#include <vector>
#include <random>
using namespace gwsz;
using std::vector;

static int nfail=0,ncheck=0;
static void check(bool ok,const char *what,double got=0,double want=0)
{
  ncheck++;
  if (!ok){nfail++; printf("FAIL %s (got %.12g, want %.12g)\n",what,got,want);}
}
static bool close(double a,double b,double tol=1e-9){return std::fabs(a-b)<=tol*std::max(1.0,std::fabs(b));}

// two layers, H=0.5 m, n=0.4, SF=0, S_fc=0.5: phimax=200 mm, phifc=100 mm, drainable porosity 0.2
static vector<sz_layer> TwoLayers()
{
  sz_layer a; a.phimax=200; a.phifc=100; a.H=0.5;
  return vector<sz_layer>(2,a);
}

int main()
{
  vector<sz_layer> L=TwoLayers();
  //-- G1 SatThickness
  { vector<double> p={100,0};   check(close(SatThickness(L,p),0.0),"G1 at field capacity",SatThickness(L,p),0.0); }
  { vector<double> p={150,0};   check(close(SatThickness(L,p),0.25),"G1 half free",SatThickness(L,p),0.25); }
  { vector<double> p={200,150}; check(close(SatThickness(L,p),0.75),"G1 bottom full + half",SatThickness(L,p),0.75); }
  { vector<double> p={200,200}; check(close(SatThickness(L,p),1.0),"G1 all full",SatThickness(L,p),1.0); }
  { vector<double> p={150,190}; check(close(SatThickness(L,p),0.475),"G1 perched water counts in proportion to the layer below (0.25+0.5*0.9*0.5)",SatThickness(L,p),0.475); }
  { vector<double> p={100,190}; check(close(SatThickness(L,p),0.0),"G1 perched water over a layer at field capacity does not count",SatThickness(L,p),0.0); }
  { vector<double> p={50,0};    check(close(SatThickness(L,p),0.0),"G1 below field capacity",SatThickness(L,p),0.0); }
  //-- G2 Fill / Drain
  { vector<double> p={100,0}; double o=Fill(L,p,120); check(close(p[0],200)&&close(p[1],20)&&close(o,0),"G2 fill 120 into (100,0) -> (200,20)",p[1],20); }
  { vector<double> p={200,150}; double r=Drain(L,p,30); check(close(p[0],200)&&close(p[1],120)&&close(r,30),"G2 drain 30 from (200,150) -> (200,120)",p[1],120); }
  { vector<double> p={200,150}; double r=Drain(L,p,500); check(close(p[0],100)&&close(p[1],100)&&close(r,150),"G2 drain never below field capacity",r,150); }
  { vector<double> p={150,190}; double r=Drain(L,p,100); check(close(p[0],100)&&close(p[1],190)&&close(r,50),"G2 drain leaves perched water",r,50); }
  { vector<double> p={190,0}; double o=Fill(L,p,500); check(close(p[0],200)&&close(p[1],200)&&close(o,290),"G5 fill beyond full -> overflow",o,290); }
  { vector<double> p={200,150}; double sh; Apply(L,p,-180,sh); check(close(p[0]+p[1],170)&&close(sh,0),"Apply: removal beyond free water taken below FC",p[0]+p[1],170); }
  //-- G4 deficit before rise: (50,0) + 60 -> level still 0, +100 more -> 0.25 m
  { vector<double> p={50,0}; Fill(L,p,40); check(close(SatThickness(L,p),0.0),"G4 deficit fill does not raise the level");
    Fill(L,p,60); check(close(SatThickness(L,p),0.25),"G4 then free water raises it",SatThickness(L,p),0.25); }

  //-- local solve: hand case. A=1e4 m2, dt=1 d, one link C=100 m2/d, zb=0, h=0.5, soil (100,0): upward flow into soil.
  // root: dV = c*C*(h - lambda), lambda = dV/1000/0.2 m (dV mm); c=1000*1/1e4=0.1 -> dV = 10*(0.5 - dV/200) -> dV=5/1.05
  {
    vector<double> p={100,0}; vector<sz_link> lk(1); lk[0].Ceff=100; lk[0].zb=0; lk[0].h=0.5;
    double dV,ovf; double lam=LocalSolve(L,p,lk,1e4,1.0,dV,ovf);
    double want=5.0/1.05;
    check(close(dV,want,1e-10),"local solve hand case dV",dV,want);
    check(close(lam,want/200.0,1e-10),"local solve hand case lambda",lam,want/200.0);
  }
  //-- full: huge head -> overflow equals excess
  {
    vector<double> p={190,190}; vector<sz_link> lk(1); lk[0].Ceff=1e4; lk[0].zb=0; lk[0].h=5.0;
    double dV,ovf; double lam=LocalSolve(L,p,lk,1e4,1.0,dV,ovf);
    // full: lambda=1, q=C*(1-5)= -4e4 m3/d up, needs 4e4 m3 = 4000 mm; room 20 mm -> overflow 3980 mm
    check(close(lam,1.0)&&close(dV,20)&&close(ovf,3980,1e-9),"G5 local solve full -> overflow",ovf,3980);
  }
  //-- drain case: saturated soil above a lower head
  {
    vector<double> p={200,150}; vector<sz_link> lk(1); lk[0].Ceff=50; lk[0].zb=0; lk[0].h=0.2;
    double dV,ovf; double lam=LocalSolve(L,p,lk,1e4,1.0,dV,ovf);
    double g=dV+0.1*50*(lam-0.2);
    check(std::fabs(g)<1e-9 && dV<0 && ovf==0,"local solve drain: residual",g,0);
  }

  //-- randomized: monotonicity of g, root residual, mass balance of Apply, contraction dlambda/dh in [0,1)
  std::mt19937 rng(12345);
  std::uniform_real_distribution<double> U(0,1);
  int bad_mono=0,bad_root=0,bad_mass=0,bad_contr=0,bad_cont=0,ncases=20000;
  for (int t=0;t<ncases;t++){
    int n=1+(int)(U(rng)*4);
    vector<sz_layer> Lr(n); vector<double> p(n);
    for (int j=0;j<n;j++){
      Lr[j].H=0.05+U(rng)*2; double cap=Lr[j].H*1000*(0.1+0.5*U(rng)); Lr[j].phimax=cap; Lr[j].phifc=cap*(0.05+0.9*U(rng));
      p[j]=U(rng)*cap*1.0;
    }
    int nl=1+(int)(U(rng)*4); vector<sz_link> lk(nl);
    for (int l=0;l<nl;l++){lk[l].Ceff=std::pow(10.0,-2+6*U(rng)); lk[l].zb=-0.5+U(rng); lk[l].h=lk[l].zb+(U(rng)-0.3)*3;
      if (lk[l].h<lk[l].zb){lk[l].Ceff=0.0;}} //contact only above the base (F=0 below it)
    double A=std::pow(10.0,2+4*U(rng)),dt=0.01+U(rng)*2;
    double c=1000*dt/A,sC=0,sR=0; for (int l=0;l<nl;l++){sC+=lk[l].Ceff; sR+=lk[l].Ceff*(lk[l].zb-lk[l].h);}
    // monotonicity on a grid of dV
    double lo=-StackFreeWater(Lr,p),hi=Room(Lr,p),gprev=-1e300;
    for (int s=0;s<=50;s++){
      double dv=lo+(hi-lo)*s/50.0; vector<double> w=p; double sh; Apply(Lr,w,dv,sh);
      double g=dv+c*(sR+sC*SatThickness(Lr,w));
      if (g<gprev-1e-9*std::max(1.0,std::fabs(g))){bad_mono++; break;} gprev=g;
    }
    { // a jump persists when the interval shrinks; a steep but continuous change does not
      double sumH=0; for (int j=0;j<n;j++){sumH+=Lr[j].H;}
      auto lamAt=[&](double dv){vector<double> w=p; double sh; Apply(Lr,w,dv,sh); return SatThickness(Lr,w);};
      for (int s=0;s<200;s++){
        double a=lo+(hi-lo)*s/200.0,b=lo+(hi-lo)*(s+1)/200.0, la=lamAt(a), lb=lamAt(b);
        if (std::fabs(lb-la)<1e-9*sumH){continue;}
        for (int k=0;k<60;k++){double m=0.5*(a+b),lm=lamAt(m); if (std::fabs(lm-la)>std::fabs(lb-lm)){b=m;lb=lm;} else {a=m;la=lm;}}
        if (std::fabs(lb-la)>1e-6*sumH){bad_cont++; break;}
      }
    }
    double dV,ovf; double lam=LocalSolve(Lr,p,lk,A,dt,dV,ovf);
    if (sC>0 && ovf==0 && dV>lo+1e-12 && dV<hi-1e-12){
      double g=dV+c*(sR+sC*lam);
      if (std::fabs(g)>1e-7*std::max(1.0,std::fabs(dV))){bad_root++;}
    }
    // mass: Apply(dV) changes total by dV - overflow
    { vector<double> w=p; double sh; double o=Apply(Lr,w,dV,sh); double s0=0,s1=0; for (int j=0;j<n;j++){s0+=p[j]; s1+=w[j];}
      if (std::fabs((s1-s0)-(dV-o))>1e-8*std::max(1.0,std::fabs(dV))+1e-9 || sh>0){bad_mass++;} }
    // contraction: perturb one head by 1 mm (only where the link is in contact and the soil is neither full nor at its floor)
    if (sC>0 && ovf==0){
      int l0=0; while (l0<nl && lk[l0].Ceff==0){l0++;}
      if (l0<nl){
        vector<sz_link> lk2=lk; lk2[l0].h+=1e-3; double dV2,o2; double lam2=LocalSolve(Lr,p,lk2,A,dt,dV2,o2);
        double d=(lam2-lam)/1e-3;
        if (o2==0 && (d<-1e-6 || d>=1.0+1e-9)){bad_contr++;}
      }
    }
  }
  check(bad_mono==0,"random: g monotone",bad_mono,0);
  check(bad_root==0,"random: root residual",bad_root,0);
  check(bad_cont==0,"random: lambda has no jumps along dV",bad_cont,0);
  check(bad_mass==0,"random: Apply mass balance",bad_mass,0);
  check(bad_contr==0,"G6 random: dlambda/dh in [0,1)",bad_contr,0);
  //-- saturated fraction
  { vector<double> z={0.0}; check(SatFraction(-0.1,z,0.5)==0.0 && SatFraction(0.6,z,0.5)==1.0 && close(SatFraction(0.25,z,0.5),0.5),"SatFraction ramp"); }
  { vector<double> z={0.0,1.0}; check(close(SatFraction(0.5,z,0.0),0.5),"SatFraction sub-grid sharp"); }
  { vector<double> z={0.0,0.3,0.7}; int bad=0;
    for (double h=-0.2;h<1.5;h+=0.0137){double d=(SatFraction(h+1e-6,z,0.5)-SatFraction(h-1e-6,z,0.5))/2e-6; if (std::fabs(d-SatFractionSlope(h,z,0.5))>1e-4){bad++;}}
    check(bad==0,"SatFractionSlope = dF/dh",bad,0); }
  { vector<double> z={0.0,0.3,0.7}; bool ok=true;
    ok&=close(ConnectedBase(-0.5,z,0.2),0.0);                       //nothing connected: the lowest base
    ok&=close(ConnectedBase(2.0,z,0.2),(0.0+0.3+0.7)/3.0);          //all connected: the mean
    for (double h=-0.2;h<1.2;h+=0.01){double b=ConnectedBase(h,z,0.2); if (SatFraction(h,z,0.2)>0 && !(b<h)){ok=false;}}
    double c1=ConnectedBase(0.3-1e-9,z,0.2),c2=ConnectedBase(0.3+1e-9,z,0.2); ok&=std::fabs(c1-c2)<1e-6;  //continuous
    check(ok,"ConnectedBase: lowest base, mean, below h when F>0, continuous"); }
  //-- G7: one link (a soil-zone column): dlambda/dh from the slope of lambda at the root = finite difference
  { std::mt19937 rng(7); std::uniform_real_distribution<double> U(0.0,1.0); int bad=0,tested=0;
    for (int it=0;it<20000;it++){
      int n=1+(int)(U(rng)*3); vector<sz_layer> Lr(n); vector<double> p(n);
      for (int j=0;j<n;j++){Lr[j].H=0.1+U(rng); Lr[j].phimax=Lr[j].H*1000*(0.2+0.3*U(rng)); Lr[j].phifc=Lr[j].phimax*(0.2+0.6*U(rng)); p[j]=Lr[j].phimax*U(rng);}
      vector<sz_link> lk(1); lk[0].Ceff=1+1e4*U(rng); lk[0].zb=0; lk[0].h=-0.5+2.5*U(rng);
      double A=1e3+1e5*U(rng),dt=0.04+U(rng),dV,ovf,lp; double lam=LocalSolve(Lr,p,lk,A,dt,dV,ovf,&lp);
      double x=1000*dt/A*lk[0].Ceff*lp, pred=x/(1+x);
      vector<sz_link> a=lk,b=lk; a[0].h-=1e-5; b[0].h+=1e-5; double d1,o1,d2,o2;
      double la=LocalSolve(Lr,p,a,A,dt,d1,o1), lb=LocalSolve(Lr,p,b,A,dt,d2,o2);
      double fd=(lb-la)/2e-5;
      if (std::fabs((lb-lam)-(lam-la))>1e-3*std::fabs(lb-la)+1e-12){continue;} //a kink inside the stencil
      tested++; if (std::fabs(fd-pred)>1e-5+1e-4*std::fabs(pred) || pred<0 || pred>=1){bad++;}
    }
    check(bad==0 && tested>10000,"G7 single link: dlambda/dh = c Ceff lambda'/(1 + c Ceff lambda')",bad,tested); }
  //-- column distribution: totals exact, bounds kept, gains never lower and losses never raise a column
  { std::mt19937 rng(11); std::uniform_real_distribution<double> U(0.0,1.0); int bad_tot=0,bad_bnd=0,bad_dir=0;
    for (int it=0;it<20000;it++){
      int n=1+(int)(U(rng)*3),nc=1+(int)(U(rng)*6); vector<sz_layer> Lr(n);
      for (int j=0;j<n;j++){Lr[j].H=0.5; Lr[j].phimax=50+200*U(rng); Lr[j].phifc=0.5*Lr[j].phimax;}
      vector<vector<double> > c(nc,vector<double>(n)); vector<double> w(nc),tg(n); double sw=0;
      for (int k=0;k<nc;k++){w[k]=(U(rng)<0.1)?0.0:U(rng); sw+=w[k];} if (sw<=0){w[0]=1; sw=1;} for (int k=0;k<nc;k++){w[k]/=sw;}
      for (int k=0;k<nc;k++){for (int j=0;j<n;j++){double r=U(rng); c[k][j]=(r<0.15)?0.0:((r<0.3)?Lr[j].phimax:Lr[j].phimax*U(rng));}}
      for (int j=0;j<n;j++){tg[j]=Lr[j].phimax*U(rng);}
      vector<vector<double> > c0=c; Distribute(Lr,c,w,tg);
      for (int j=0;j<n;j++){
        double m=0,m0=0; for (int k=0;k<nc;k++){m+=w[k]*c[k][j]; m0+=w[k]*c0[k][j];}
        if (std::fabs(m-tg[j])>1e-9*Lr[j].phimax){bad_tot++;}
        for (int k=0;k<nc;k++){
          if (c[k][j]<-1e-9 || c[k][j]>Lr[j].phimax*(1+1e-12)+1e-9){bad_bnd++;}
          if ((tg[j]>m0 && c[k][j]<c0[k][j]-1e-12) || (tg[j]<m0 && c[k][j]>c0[k][j]+1e-12)){bad_dir++;}
        }
      }
    }
    check(bad_tot==0,"Distribute: area-weighted totals equal the targets",bad_tot,0);
    check(bad_bnd==0,"Distribute: every column stays within [0, phimax]",bad_bnd,0);
    check(bad_dir==0,"Distribute: gains never lower, losses never raise a column",bad_dir,0); }
  printf("soil-zone unit tests: %d checks, %d failed (%d random cases)\n",ncheck,nfail,ncases);
  return nfail?1:0;
}
