// Unit tests of the soil-zone interface functions (src/GWSoilZone.cpp): G1-G7 plus randomized checks.
// build: g++ -std=c++11 -O2 -I$RAVEN_SRC/src soilzone_unit.cpp $RAVEN_SRC/src/GWSoilZone.cpp -o soilzone_unit
#include "GWSoilZone.h"
#include <cstdio>
#include <cmath>
#include <cstdlib>
#include <vector>
#include <random>
#include <algorithm>
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

  //-- local solve: hand case. A=1e4 m2, dt=1 d, one sample (zb=0), step connection, C=100 m2/d, h=0.5, soil (100,0):
  // upward flow into soil. root: dV = c*C*(h - lambda), lambda = dV/1000/0.2 m (dV mm); c=0.1 -> dV = 10*(0.5 - dV/200)
  sz_cell one; one.zbs=vector<double>(1,0.0); one.ds=0.0; one.D=1.0; one.C=100.0;
  {
    vector<double> p={100,0}; double dV,ovf,lp; double lam=LocalSolve(L,p,one,0.5,0.5,1e4,1.0,dV,ovf,lp);
    double want=5.0/1.05;
    check(close(dV,want,1e-10),"local solve hand case dV",dV,want);
    check(close(lam,want/200.0,1e-10),"local solve hand case lambda",lam,want/200.0);
    check(close(lp,1.0/200.0,1e-9),"local solve hand case dlambda/dV",lp,1.0/200.0);
  }
  //-- full: huge head -> overflow equals excess
  {
    sz_cell c1=one; c1.C=1e4;
    vector<double> p={190,190}; double dV,ovf,lp; double lam=LocalSolve(L,p,c1,5.0,5.0,1e4,1.0,dV,ovf,lp);
    // full: lambda=1, q=C*(1-5)= -4e4 m3/d up, needs 4e4 m3 = 4000 mm; room 20 mm -> overflow 3980 mm
    check(close(lam,1.0)&&close(dV,20)&&close(ovf,3980,1e-9)&&(lp==0.0),"G5 local solve full -> overflow",ovf,3980);
  }
  //-- drain case: saturated soil above a lower head
  {
    sz_cell c1=one; c1.C=50;
    vector<double> p={200,150}; double dV,ovf,lp; double lam=LocalSolve(L,p,c1,0.2,0.2,1e4,1.0,dV,ovf,lp);
    double g=dV+0.1*50*(lam-0.2);
    check(std::fabs(g)<1e-9 && dV<0 && ovf==0,"local solve drain: residual",g,0);
  }
  //-- sub-grid level: inverse pair, limits, slope
  {
    sz_cell c; c.zbs={0.0,0.2,0.2,0.9,1.5}; c.ds=0.3; c.D=1.0; c.C=1.0; bool ok=true;
    for (double lam=0.0;lam<=1.0;lam+=0.01){double Lv=SubgridLevel(c,lam); if (std::fabs(SubgridThickness(c,Lv)-lam)>1e-12){ok=false;}}
    ok&=close(SubgridLevel(c,0.0),0.0) && close(SubgridLevel(c,1.0),2.5);
    for (double lam=0.013;lam<0.99;lam+=0.0371){double d; double Lv=SubgridLevel(c,lam,&d); double fd=(SubgridLevel(c,lam+1e-7)-SubgridLevel(c,lam-1e-7))/2e-7;
      if (std::fabs(fd-d)>1e-5*std::max(1.0,d) && std::fabs(SubgridThickness(c,Lv+1e-6)-SubgridThickness(c,Lv-1e-6))>1e-9){ok=false;}}
    check(ok,"SubgridLevel: inverse of SubgridThickness, limits, dLv/dlam");
  }
  //-- sub-grid flux: one sample is the plain link; derivatives; continuity in h (a sample joins at its own base)
  {
    double F,qh,qc,ql;
    double q=SubgridFlux(one,0.3,0.5,0.5,F,qh,qc,ql);
    check(close(q,100*(0.3-0.5))&&close(F,1.0)&&close(qh,-100)&&close(ql,100),"SubgridFlux one sample = C (zb + lambda - h)",q,-20);
    sz_cell c; c.zbs={0.0,0.2,0.2,0.9,1.5}; c.ds=0.3; c.D=1.0; c.C=7.0; int bad=0,badj=0;
    for (double lam=0.05;lam<1.0;lam+=0.11){
      for (double h=-0.4;h<3.0;h+=0.0137){
        double q0=SubgridFlux(c,lam,h,h,F,qh,qc,ql),q1=SubgridFlux(c,lam,h+1e-7,h+1e-7,F,qh,qc,ql),q2=SubgridFlux(c,lam,h-1e-7,h-1e-7,F,qh,qc,ql);
        double fdh=(q1-q2)/2e-7; SubgridFlux(c,lam,h,h,F,qh,qc,ql);
        double l1=SubgridFlux(c,lam+1e-7,h,h,F,qh,qc,ql),l2=SubgridFlux(c,lam-1e-7,h,h,F,qh,qc,ql); double fdl=(l1-l2)/2e-7; SubgridFlux(c,lam,h,h,F,qh,qc,ql);
        bool kink=std::fabs((q1-q0)-(q0-q2))>1e-6*std::fabs(q1-q2)+1e-12 || std::fabs((l1-q0)-(q0-l2))>1e-6*std::fabs(l1-l2)+1e-12;
        if (!kink && (std::fabs(fdh-(qh+qc))>1e-4*std::max(1.0,std::fabs(qh+qc)) || std::fabs(fdl-ql)>1e-4*std::max(1.0,std::fabs(ql)))){bad++;}
        if (std::fabs(q1-q2)>1e-4){badj++;}   //no jump in h
      }
    }
    check(bad==0,"SubgridFlux: dq/dh and dq/dlam match finite differences",bad,0);
    check(badj==0,"SubgridFlux: continuous in h (samples join at their own base, even with ds=0.3)",badj,0);
    int badj0=0; //straddle every sample base exactly (also where perched water stands above it)
    for (double lam=0.05;lam<1.0;lam+=0.11){for (size_t i=0;i<c.zbs.size();i++){double z=c.zbs[i];
      double q1=SubgridFlux(c,lam,z+1e-9,z+1e-9,F,qh,qc,ql),q2=SubgridFlux(c,lam,z-1e-9,z-1e-9,F,qh,qc,ql); if (std::fabs(q1-q2)>1e-6){badj0++;}}}
    check(badj0==0,"SubgridFlux: continuous in h across each sample base (ds>0)",badj0,0);
  }

  //-- randomized: monotonicity of g, root residual, mass balance of Apply, dlambda/dh in [0,1), Robin slope
  std::mt19937 rng(12345);
  std::uniform_real_distribution<double> U(0,1);
  int bad_mono=0,bad_root=0,bad_mass=0,bad_contr=0,bad_cont=0,bad_slope=0,nslope=0,ncases=20000;
  for (int t=0;t<ncases;t++){
    int n=1+(int)(U(rng)*4);
    vector<sz_layer> Lr(n); vector<double> p(n); double D=0;
    for (int j=0;j<n;j++){
      Lr[j].H=0.05+U(rng)*2; double cap=Lr[j].H*1000*(0.1+0.5*U(rng)); Lr[j].phimax=cap; Lr[j].phifc=cap*(0.05+0.9*U(rng));
      p[j]=U(rng)*cap*1.0; D+=Lr[j].H;
    }
    sz_cell cl; int ns=1+(int)(U(rng)*9); for (int k=0;k<ns;k++){cl.zbs.push_back(-1.0+2.0*U(rng));} std::sort(cl.zbs.begin(),cl.zbs.end());
    cl.ds=(U(rng)<0.2)?0.0:0.01+U(rng); cl.D=D; cl.C=std::pow(10.0,-2+6*U(rng));
    double h=-1.5+(4.0+D)*U(rng);
    double A=std::pow(10.0,2+4*U(rng)),dt=0.01+U(rng)*2,c=1000*dt/A,F,qh,qc,ql;
    auto gAt=[&](double dv,double hh){vector<double> w=p; double sh; Apply(Lr,w,dv,sh); return dv+c*SubgridFlux(cl,SatThickness(Lr,w),hh,hh,F,qh,qc,ql);};
    // monotonicity on a grid of dV
    double lo=-StackFreeWater(Lr,p),hi=Room(Lr,p),gprev=-1e300;
    for (int s=0;s<=50;s++){
      double dv=lo+(hi-lo)*s/50.0, g=gAt(dv,h);
      if (g<gprev-1e-9*std::max(1.0,std::fabs(g))){bad_mono++; break;} gprev=g;
    }
    { // a jump persists when the interval shrinks; a steep but continuous change does not
      double sumH=D;
      auto lamAt=[&](double dv){vector<double> w=p; double sh; Apply(Lr,w,dv,sh); return SatThickness(Lr,w);};
      for (int s=0;s<200;s++){
        double a=lo+(hi-lo)*s/200.0,b=lo+(hi-lo)*(s+1)/200.0, la=lamAt(a), lb=lamAt(b);
        if (std::fabs(lb-la)<1e-9*sumH){continue;}
        for (int k=0;k<60;k++){double m=0.5*(a+b),lm=lamAt(m); if (std::fabs(lm-la)>std::fabs(lb-lm)){b=m;lb=lm;} else {a=m;la=lm;}}
        if (std::fabs(lb-la)>1e-6*sumH){bad_cont++; break;}
      }
    }
    double dV,ovf,lp; double lam=LocalSolve(Lr,p,cl,h,h,A,dt,dV,ovf,lp);
    double q=SubgridFlux(cl,lam,h,h,F,qh,qc,ql);
    if (F>0 && ovf==0 && dV>lo+1e-12 && dV<hi-1e-12){
      double g=dV+c*q;
      if (std::fabs(g)>1e-7*std::max(1.0,std::fabs(dV))){bad_root++;}
    }
    // mass: Apply(dV) changes total by dV - overflow
    { vector<double> w=p; double sh; double o=Apply(Lr,w,dV,sh); double s0=0,s1=0; for (int j=0;j<n;j++){s0+=p[j]; s1+=w[j];}
      if (std::fabs((s1-s0)-(dV-o))>1e-8*std::max(1.0,std::fabs(dV))+1e-9 || sh>0){bad_mass++;} }
    // perturb the head by 1e-5 m: dlambda/dh and the total slope dq/dh = q_h/(1 + c q_lam lambda') of the boundary
    // MODFLOW gets match finite differences (lambda can fall as h rises: a rising water table connects more samples, and
    // where the soil water stands above the water table they drain into the aquifer)
    if (F>0 && ovf==0){
      double dV2,o2,lp2,dV3,o3,lp3;
      double lam2=LocalSolve(Lr,p,cl,h+1e-5,h+1e-5,A,dt,dV2,o2,lp2),lam3=LocalSolve(Lr,p,cl,h-1e-5,h-1e-5,A,dt,dV3,o3,lp3);
      double F2,F3,a1,a2,a3;
      double q2=SubgridFlux(cl,lam2,h+1e-5,h+1e-5,F2,a1,a3,a2),q3=SubgridFlux(cl,lam3,h-1e-5,h-1e-5,F3,a1,a3,a2);
      double d=(lam2-lam3)/2e-5;
      double qmid=0.5*(q2+q3);
      bool smooth=std::fabs(qmid-q)<1e-7*std::max(1.0,std::fabs(q)) && std::fabs(0.5*(lam2+lam3)-lam)<1e-9*std::max(1.0,lam);
      if (o2==0 && o3==0 && smooth){
        nslope++;
        double dl=-lp*c*(qh+qc)/(1.0+c*ql*lp);   //implicit function theorem on dV + c q(lambda(dV),h) = 0
        if (std::fabs(d-dl)>1e-3*std::max(std::fabs(dl),1e-9)+1e-9){bad_contr++;}
        double pred=(qh+qc)/(1.0+c*ql*lp), fd=(q2-q3)/2e-5;
        if (std::fabs(fd-pred)>1e-3*std::max(std::fabs(pred),1e-6*cl.C)+1e-8){bad_slope++;}
      }
    }
  }
  check(bad_mono==0,"random: g monotone",bad_mono,0);
  check(bad_root==0,"random: root residual",bad_root,0);
  check(bad_cont==0,"random: lambda has no jumps along dV",bad_cont,0);
  check(bad_mass==0,"random: Apply mass balance",bad_mass,0);
  check(bad_contr<=nslope/1000,"G6 random: dlambda/dh = -lambda' c q_h/(1 + c q_lam lambda') (finite difference)",bad_contr,nslope);
  check(bad_slope<=nslope/1000 && nslope>5000,"G7 random: boundary slope dq/dh = q_h/(1 + c q_lam lambda') (finite difference)",bad_slope,nslope);
  //-- connected fraction
  { vector<double> z={0.0}; check(SatFraction(-0.1,z,0.5)==0.0 && SatFraction(0.6,z,0.5)==1.0 && close(SatFraction(0.25,z,0.5),0.5),"SatFraction ramp: through ds above the base"); }
  { sz_cell c1; c1.zbs={0.0}; c1.D=1.0; c1.ds=0.5; c1.C=10.0; double F,qh,qc,ql;
    SubgridFlux(c1,0.0,0.0,0.0,F,qh,qc,ql); double F0=F; SubgridFlux(c1,0.0,-0.25,-0.25,F,qh,qc,ql); double Fm=F; SubgridFlux(c1,0.0,-0.6,-0.6,F,qh,qc,ql);
    check(F0==1.0 && close(Fm,0.5) && F==0.0,"contact weights: through ds below the base, full at it",Fm,0.5); }
  { vector<double> z={0.0,1.0}; check(close(SatFraction(0.5,z,0.0),0.5),"SatFraction sub-grid sharp"); }
  //-- column distribution: mass (totals + overflow), bounds, layer totals, the rules for recharge, percolation, losses, gains
  { std::mt19937 rng(11); std::uniform_real_distribution<double> U(0.0,1.0);
    int bad_mass=0,bad_bnd=0,bad_tot=0,bad_rfw=0,bad_rar=0,bad_loss=0,bad_gain=0,bad_vert=0,bad_lr=0;
    for (int it=0;it<20000;it++){
      int n=1+(int)(U(rng)*3),nc=1+(int)(U(rng)*6); vector<sz_layer> Lr(n);
      for (int j=0;j<n;j++){Lr[j].H=0.5; Lr[j].phimax=50+200*U(rng); Lr[j].phifc=0.5*Lr[j].phimax;}
      vector<vector<double> > c(nc,vector<double>(n)); vector<double> w(nc),tg(n); double sw=0;
      for (int k=0;k<nc;k++){w[k]=(U(rng)<0.1)?0.0:U(rng); sw+=w[k];} if (sw<=0){w[0]=1; sw=1;} for (int k=0;k<nc;k++){w[k]/=sw;}
      for (int k=0;k<nc;k++){for (int j=0;j<n;j++){double r=U(rng); c[k][j]=(r<0.15)?0.0:((r<0.3)?Lr[j].phimax:Lr[j].phimax*U(rng));}}
      vector<double> m0(n,0.0); for (int j=0;j<n;j++){for (int k=0;k<nc;k++){m0[j]+=w[k]*c[k][j];}}
      for (int j=0;j<n;j++){tg[j]=Lr[j].phimax*U(rng);}
      double R=(U(rng)<0.5)?std::min(m0[0],20.0*U(rng)):0.0; bool byA=(U(rng)<0.5);
      vector<vector<double> > c0=c; vector<double> lr; double ovf=Distribute(Lr,c,w,tg,0,R,byA,&lr);
      double sumT=0,sumA=0,sumL=0; for (int j=0;j<n;j++){sumT+=tg[j]; for (int k=0;k<nc;k++){sumA+=w[k]*c[k][j];}}
      for (int k=0;k<nc;k++){sumL+=w[k]*lr[k];}
      if (std::fabs(sumA+ovf-sumT)>1e-9*(1+sumT) || ovf<-1e-12){bad_mass++;}
      if (std::fabs(sumL-R)>1e-9*(1+R)){bad_lr++;}
      bool full=false; for (int k=0;k<nc;k++){for (int j=0;j<n;j++){if (c[k][j]>=Lr[j].phimax*(1-1e-12)){full=true;}}}
      for (int j=0;j<n;j++){
        for (int k=0;k<nc;k++){if (c[k][j]<-1e-9 || c[k][j]>Lr[j].phimax*(1+1e-12)+1e-9){bad_bnd++;}}
        if (!full && ovf<=0.0){double m=0; for (int k=0;k<nc;k++){m+=w[k]*c[k][j];} if (std::fabs(m-tg[j])>1e-9*Lr[j].phimax){bad_tot++;}}
      }
      if (n==1){ //single layer: recharge first (free water first or by area), then the rest alike
        double d=tg[0]-m0[0]+R;   //change after the recharge
        double fw=0; for (int k=0;k<nc;k++){fw+=w[k]*std::max(c0[k][0]-Lr[0].phifc,0.0);}
        double minw=1e300; for (int k=0;k<nc;k++){if (w[k]>0){minw=std::min(minw,c0[k][0]);}}
        if (R>0 && !byA && R<=fw){ //drained from free water first: a column at field capacity gives nothing
          for (int k=0;k<nc;k++){if (c0[k][0]<=Lr[0].phifc && lr[k]>1e-9){bad_rfw++;}}}
        if (R>0 && byA && R<=minw){ //by area: every column gives the same depth
          for (int k=0;k<nc;k++){if (w[k]>0 && std::fabs(lr[k]-R)>1e-9*(1+R)){bad_rar++;}}}
        if (d<0 && R==0 && -d<=minw){ //other losses alike
          for (int k=0;k<nc;k++){if (w[k]>0 && std::fabs((c0[k][0]-c[k][0])+d)>1e-9*Lr[0].phimax){bad_loss++;}}}
        if (d>0 && R==0){bool room=true; for (int k=0;k<nc;k++){if (c0[k][0]+d>Lr[0].phimax){room=false;}}
          if (room){for (int k=0;k<nc;k++){if (w[k]>0 && std::fabs((c[k][0]-c0[k][0])-d)>1e-9*Lr[0].phimax){bad_gain++;}}}}
      }
      if (n==2 && R==0){ //percolation stays in its column: upper loses, lower gains, nothing full -> lower gains only where upper lost
        double du=tg[1]-m0[1],dl=tg[0]-m0[0];
        if (du<0 && dl>0 && -du>=dl && ovf<=0){
          for (int k=0;k<nc;k++){double gl=c[k][0]-c0[k][0],lu=c0[k][1]-c[k][1]; if (w[k]>0 && gl>lu+1e-9*Lr[0].phimax){bad_vert++;}}}
      }
    }
    check(bad_mass==0,"Distribute: column totals plus overflow equal the targets",bad_mass,0);
    check(bad_lr==0,"Distribute: the columns' parts of the recharge add up to it",bad_lr,0);
    check(bad_bnd==0,"Distribute: every column stays within [0, phimax]",bad_bnd,0);
    check(bad_tot==0,"Distribute: layer totals exact where nothing is full",bad_tot,0);
    check(bad_rfw==0,"Distribute: recharge of a drainage comes from free water first",bad_rfw,0);
    check(bad_rar==0,"Distribute: recharge of a constant rate comes from every column alike",bad_rar,0);
    check(bad_loss==0,"Distribute: other losses (evaporation) alike on every column",bad_loss,0);
    check(bad_gain==0,"Distribute: a gain falls alike on every column",bad_gain,0);
    check(bad_vert==0,"Distribute: percolation stays in its column",bad_vert,0); }
  { //Raven applies its processes in order on the HRU mean: rain into the top layer, percolation down the layers, then
    //recharge out of the bottom one (it can exceed what the bottom layer held at the start) and evaporation
    std::mt19937 rng(23); std::uniform_real_distribution<double> U(0.0,1.0); int bad_neg=0,bad_m=0,bad_r=0,bad_mv1=0,bad_mvn=0;
    for (int it=0;it<200000;it++){
      int n=1+(int)(U(rng)*3),nc=1+(int)(U(rng)*6); vector<sz_layer> Lr(n);
      for (int j=0;j<n;j++){Lr[j].H=0.5; Lr[j].phimax=50+200*U(rng); Lr[j].phifc=Lr[j].phimax*(0.2+0.6*U(rng));}
      vector<vector<double> > c(nc,vector<double>(n)); vector<double> w(nc); double sw=0;
      for (int k=0;k<nc;k++){w[k]=0.05+U(rng); sw+=w[k];} for (int k=0;k<nc;k++){w[k]/=sw;}
      for (int k=0;k<nc;k++){for (int j=0;j<n;j++){double r=U(rng); c[k][j]=(r<0.2)?0.0:((r<0.4)?Lr[j].phimax:Lr[j].phimax*U(rng));}}
      vector<double> m(n,0.0); for (int j=0;j<n;j++){for (int k=0;k<nc;k++){m[j]+=w[k]*c[k][j];}}
      m[n-1]=std::min(m[n-1]+30.0*U(rng),Lr[n-1].phimax);                      //rain
      for (int j=n-1;j>=1;j--){double p=U(rng)*m[j]; p=std::min(p,Lr[j-1].phimax-m[j-1]); m[j]-=p; m[j-1]+=p;} //percolation
      double R=U(rng)*m[0]; m[0]-=R;                                             //recharge
      m[n-1]-=U(rng)*0.5*m[n-1];                                                 //evaporation
      bool byA=(U(rng)<0.5); vector<double> lr; vector<vector<double> > c0=c;
      double mv=-1.0; double o=Distribute(Lr,c,w,m,0,R,byA,&lr,&mv);
      if ((n==1) && (mv!=0.0)){bad_mv1++;} if (!(mv>=0.0)){bad_mvn++;}
      double sa=0,st=0,sl=0; for (int j=0;j<n;j++){st+=m[j]; for (int k=0;k<nc;k++){sa+=w[k]*c[k][j]; if (c[k][j]<-1e-9){bad_neg++;}}}
      for (int k=0;k<nc;k++){sl+=w[k]*lr[k];}
      if (std::fabs(sa+o-st)>1e-9*(1+st)){bad_m++;} if (std::fabs(sl-R)>1e-9*(1+R)){bad_r++;}
    }
    check(bad_neg==0,"Distribute (Raven's process order): no column goes below 0",bad_neg,0);
    check(bad_m==0,"Distribute (Raven's process order): mass",bad_m,0);
    check(bad_r==0,"Distribute (Raven's process order): recharge parts add up",bad_r,0);
    check(bad_mv1==0,"Distribute: no layer redistribution with a single layer (not even round-off)",bad_mv1,0);
    check(bad_mvn==0,"Distribute: layer redistribution never negative",bad_mvn,0); }
  { vector<sz_layer> L2=TwoLayers(); vector<vector<double> > c(2,vector<double>(2)); vector<double> w={0.5,0.5};
    c[0][0]=L2[0].phimax; c[0][1]=L2[1].phimax; c[1][0]=L2[0].phifc; c[1][1]=L2[1].phifc;   //a full and a dry column
    vector<double> tg={0.5*(c[0][0]+c[1][0]),0.5*(c[0][1]+c[1][1])+20.0};                   //20 mm of rain on the top layer
    double o=Distribute(L2,c,w,tg);
    check(close(o,10.0) && close(c[1][1],L2[1].phifc+20.0) && c[0][1]==L2[1].phimax,"Distribute: rain on a full column overflows, not moved to the dry one",o,10.0); }
  //-- edge cases
  { vector<sz_layer> L2=TwoLayers(); vector<double> p={L2[0].phimax+10.0,0.0}; double tot0=p[0]+p[1];
    double o=Fill(L2,p,10.0); check(close(p[0]+p[1]+o,tot0+10.0),"Fill keeps water above capacity in an overfull layer",p[0]+p[1]+o,tot0+10.0); }
  { vector<sz_layer> L3(3); L3[0]={200,100,1}; L3[1]={0,0,0}; L3[2]={200,100,1}; vector<double> p={200,0,150};
    double l=SatThickness(L3,p); check(std::isfinite(l),"SatThickness finite for a layer without free-water capacity",l,0);
    vector<sz_layer> L4(1); L4[0]={100,100,1}; vector<double> p4={100}; check(SatThickness(L4,p4)==1.0,"SatThickness of a full layer at phimax==phifc",SatThickness(L4,p4),1.0); }
  { sz_cell cb; cb.zbs={0.0,0.2}; cb.D=1.0; cb.ds=0.0; cb.C=10.0; double F,qh,qc,ql;
    SubgridFlux(cb,0.1,2.0,2.0,F,qh,qc,ql); check(close(ql,10.0),"q_lam at a breakpoint of the soil water level",ql,10.0); }
  { vector<sz_layer> L2=TwoLayers(); vector<vector<double> > c(2,vector<double>(2,50.0)); vector<double> w={0.45,0.45},tg={L2[0].phimax*1.1,10.0};
    double o=Distribute(L2,c,w,tg); double tot=w[0]*(c[0][0]+c[0][1])+w[1]*(c[1][0]+c[1][1]);
    check(close(tot+o,tg[0]+tg[1]),"Distribute: mass kept for weights not summing to 1",tot+o,tg[0]+tg[1]); }
  { // connection head above the water table (secant/regula falsi steps): never drains more than the column holds, q_hc
    // matches finite differences, and the local balance holds
    std::mt19937 rg(777); std::uniform_real_distribution<double> V(0,1); int bshort=0,broot=0,bqc=0,nqc=0;
    for (int t=0;t<20000;t++){
      int n=1+(int)(V(rg)*3); vector<sz_layer> Lr(n); vector<double> p(n); double D=0;
      for (int j=0;j<n;j++){Lr[j].H=0.05+V(rg); double cap=Lr[j].H*1000*(0.1+0.5*V(rg)); Lr[j].phimax=cap; Lr[j].phifc=cap*(0.05+0.9*V(rg)); p[j]=V(rg)*cap; D+=Lr[j].H;}
      sz_cell cl; int ns=1+(int)(V(rg)*9); for (int k=0;k<ns;k++){cl.zbs.push_back(-1.0+2.0*V(rg));} std::sort(cl.zbs.begin(),cl.zbs.end());
      cl.ds=(V(rg)<0.2)?0.0:0.01+V(rg); cl.D=D; cl.C=std::pow(10.0,-2+6*V(rg));
      double h=-1.5+3.0*V(rg),hc=h+(V(rg)-0.3)*1.5,A=std::pow(10.0,2+4*V(rg)),dt=0.01+V(rg)*2,c=1000*dt/A;
      double dV,ovf,lp,F,qh,qc,ql; double lam=LocalSolve(Lr,p,cl,h,hc,A,dt,dV,ovf,lp);
      double q=SubgridFlux(cl,lam,h,hc,F,qh,qc,ql);
      vector<double> w=p; double sh; Apply(Lr,w,-c*q-ovf,sh);  //book the solved exchange (and the overflow) on the column
      if (sh>1e-9*std::max(1.0,c*std::fabs(q))){bshort++;}
      if (ovf==0 && std::fabs(dV+c*q)>1e-7*std::max(1.0,std::fabs(dV))){broot++;}
      if (cl.ds>0){double e=1e-6,a1,a2,a3,F1; double q1=SubgridFlux(cl,lam,h,hc+e,F1,a1,a2,a3),q2=SubgridFlux(cl,lam,h,hc-e,F1,a1,a2,a3);
        double qm=SubgridFlux(cl,lam,h,hc,F1,a1,a2,a3);
        if (std::fabs((q1-qm)-(qm-q2))<1e-6*std::fabs(q1-q2)+1e-12){nqc++; if (std::fabs((q1-q2)/(2*e)-qc)>1e-4*std::max(1.0,std::fabs(qc))){bqc++;}}}
    }
    check(bshort==0,"hc > h: the solved exchange never exceeds the column's water",bshort,0);
    check(broot==0,"hc != h: local balance dV + c q = 0",broot,0);
    check(bqc==0 && nqc>1000,"q_hc matches finite differences",bqc,nqc); }
  printf("soil-zone unit tests: %d checks, %d failed (%d random cases)\n",ncheck,nfail,ncases);
  return nfail?1:0;
}
