// Unit tests of the KINEMATIC unsaturated column (GWVadoseKW.cpp) and of the column library parts it relies on
// (GWVadose.cpp: reference ths - Sy in Build/MoveBottom/RelStorage, the capped grid, the inactive-column contract).
// Build: g++ -O2 -std=c++11 -I<src> vadose_kw_unit.cpp <src>/GWVadose.cpp <src>/GWVadoseKW.cpp -o vadose_kw_unit
// Prints "kinematic unit tests: N checks, 0 failed" when everything holds; "K1 ..." lines carry the numbers the manual
// quotes (front arrival and drainage tail against the analytical kinematic wave, with grid refinement).
#include "GWVadose.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <chrono>
#include <algorithm>
#include <random>
using namespace gwvz;
static int nfail=0,ncheck=0;
static void check(bool ok,const char *what,double got=0,double want=0)
{
  ncheck++; if (!ok){nfail++; printf("  FAIL %s (got %.10g, want %.10g)\n",what,got,want);}
}
static vz_mat Mat(double ths,double b,double psia,double Ks,double Sy){vz_mat m; m.ths=ths; m.b=b; m.psia=psia; m.Ks=Ks; m.Sy=Sy; m.Ss=1e-5; return m;}
static vz_strat One(const vz_mat &m){vz_strat s; s.ztop.push_back(1e9); s.zbot.push_back(-1e9); s.mat.push_back(m); return s;}
static vz_strat Two(const vz_mat &a,const vz_mat &b,double zi){vz_strat s; s.ztop={1e9,zi}; s.zbot={zi,-1e9}; s.mat={a,b}; return s;}
static double thr(const vz_mat &m){return m.ths-m.Sy;}
static bool finite_all(const vz_column &c){for (double t:c.th){if (!std::isfinite(t)){return false;}} for (double p:c.psi){if (!std::isfinite(p)){return false;}} return true;}

// analytical kinematic wave in a uniform column, K(th) = A [(th/ths)^e - x0^e]
struct kwa
{
  double ths,thr,e,A,Ks,x0e;
  kwa(const vz_mat &m){ths=m.ths; thr=m.ths-m.Sy; e=2*m.b+3; x0e=std::pow(thr/ths,e); A=m.Ks/(1-x0e); Ks=m.Ks;}
  double K(double th) const {return A*(std::pow(th/ths,e)-x0e);}
  double thq(double q) const {return ths*std::pow(x0e+q/A,1.0/e);}
  double c(double th) const {return A*e*std::pow(th/ths,e-1)/ths;}
  double thc(double cc) const {return ths*std::pow(cc*ths/(A*e),1.0/(e-1));}
};

// uncapped grid of the hooks build (weights 1.3^min(j,h)), to check that N <= 18 is unchanged bit for bit
static std::vector<double> OldGrid(double L,int Nmax)
{
  int N=(int)std::ceil(L/0.05); N=std::max(3,std::min(N,std::max(Nmax,3)));
  std::vector<double> w(N),dz(N); const double r=1.3; int h=(N+1)/2;
  for (int k=0;k<N;k++){int j=std::min(k,N-1-k); w[k]=std::pow(r,(double)std::min(j,h));}
  double sw=0.0; for (int k=0;k<N;k++){sw+=w[k];}
  for (int k=0;k<N;k++){dz[k]=L*w[k]/sw;}
  return dz;
}

int main()
{
  //-- 1. the grid: N = 3..18 bit for bit as before, from N = 19 the cap (1.3^8) fills the middle ----------------------
  {
    SetReference(0); vz_strat S=One(Mat(0.35,4,0.3,1.0,0.2));
    int same=0,diff=0;
    for (int N=3;N<=40;N++){
      vz_column c; Build(c,S,10.0,0.0,N); std::vector<double> o=OldGrid(10.0,N);
      bool eq=(o.size()==c.dz.size()); for (size_t i=0;eq && i<o.size();i++){eq=(o[i]==c.dz[i]);}
      if (N<=18){check(eq,"grid N<=18 unchanged",N,0); same+=eq;} else {diff+=!eq;}
      const double mx=*std::max_element(c.dz.begin(),c.dz.end()),mn=*std::min_element(c.dz.begin(),c.dz.end());
      check(mx/mn<=std::pow(1.3,8)*(1+1e-12),"grid ratio capped at 1.3^8",mx/mn,std::pow(1.3,8));
      double s=0; for (double d:c.dz){s+=d;} check(std::fabs(s-10.0)<1e-12,"grid sums to L",s,10.0);
      if (N>=24){check(std::fabs(mx-10.0/(N-10))<0.1*10.0/(N-10),"middle thickness about L/(N-10)",mx,10.0/(N-10));}
    }
    check(diff==22,"grid N>=19 differs from the uncapped one",diff,22);
    vz_column c16; Build(c16,S,2.4,0.0,16); check(std::fabs(c16.dz[0]-0.05)<0.002,"N=16, L=2.4 m: end node 5 cm",c16.dz[0],0.05);
    vz_column c200; Build(c200,S,10.0,0.0,200); double mn=1e9; for (double d:c200.dz){mn=std::min(mn,d);}
    printf("grid: N=3..18 identical to the uncapped grid; L=10 m, N=200 thinnest node %.3g m (uncapped 6e-12 m)\n",mn);
    check(mn>0.005,"N=200 thinnest node not degenerate",mn,0.005);
  }

  //-- 2. reference ths - Sy: Build, RelStorage, MoveBottom (nothing exchanged when falling; Sy dh at most when rising)
  {
    SetReference(1);
    vz_mat m=Mat(0.35,4,0.3,0.5,0.2),m2=Mat(0.45,8,0.5,0.01,0.05);
    for (int lay=0;lay<2;lay++){
      vz_strat S=lay?Two(m,m2,3.0):One(m);
      vz_column c; double r0=Build(c,S,6.0,0.0,16);
      bool atr=true; for (size_t i=0;i<c.th.size();i++){atr&=(c.th[i]==thr(S.mat[c.im[i]]));}
      check(atr && r0==0.0 && RelStorage(c,S)==0.0,"KW Build at ths - Sy, relative storage 0",r0,0);
      //wet the column a little, then move the bottom down: nothing exchanged, the excess unchanged
      double rej; for (int k=0;k<5;k++){StepKinematic(c,S,1.0,0.02,rej);}
      const double R1=RelStorage(c,S);
      double ab=MoveBottom(c,S,-1.5,16);
      check(ab==0.0,"KW falling water table: nothing exchanged",ab,0);
      check(std::fabs(RelStorage(c,S)-R1)<1e-14,"KW falling water table: excess kept",RelStorage(c,S),R1);
      check(std::fabs(c.th.back()-thr(S.mat[c.im.back()]))<1e-15,"KW new bottom node at ths - Sy",c.th.back(),thr(S.mat[c.im.back()]));
      //rising water table: what is released is the excess below it, at most the integral of Sy dh (th <= ths)
      vz_column c2=c; const double z1=lay?3.6:1.0;
      ab=MoveBottom(c2,S,z1,16);
      check(ab>=0.0 && ab<=SyRise(S,-1.5,z1)+1e-15,"KW rising water table releases at most Sy dh",ab,SyRise(S,-1.5,z1));
      check(std::fabs(RelStorage(c2,S)+ab-RelStorage(c,S))<1e-13,"KW rising water table conserves",RelStorage(c2,S)+ab,RelStorage(c,S));
      //a saturated column under a rising water table releases exactly Sy dh (one material)
      if (!lay){
        vz_column c3; Build(c3,S,6.0,0.0,16); for (size_t i=0;i<c3.th.size();i++){c3.th[i]=m.ths;}
        ab=MoveBottom(c3,S,2.0,16); check(std::fabs(ab-0.2*2.0)<1e-12,"KW saturated column releases Sy dh",ab,0.4);
      }
      vz_column c4=c; const double Rc=RelStorage(c4,S); ab=MoveBottom(c4,S,7.0,16);
      check(!c4.active && std::fabs(ab-Rc)<1e-15,"KW column gone: its excess released",ab,Rc);
    }
    check(std::fabs(SyRise(Two(Mat(0.35,4,.3,1,0.30),Mat(0.35,4,.3,1,0.05),5.0),4.9,6.0)-(0.1*0.05+1.0*0.30))<1e-14,"SyRise across a layer boundary",
          SyRise(Two(Mat(0.35,4,.3,1,0.30),Mat(0.35,4,.3,1,0.05),5.0),4.9,6.0),0.305);
    //the hydrostatic reference (RICHARDS, LAG) unchanged
    SetReference(0);
    vz_strat S=One(m); vz_column c; double r0=Build(c,S,6.0,0.0,16);
    bool eq=true; for (size_t i=0;i<c.th.size();i++){eq&=(c.psi[i]==0.0-c.zc[i]) && (c.th[i]==Theta(m,c.psi[i]));}
    check(eq && std::fabs(r0)<1e-15,"hydrostatic reference: Build unchanged",r0,0);
  }

  //-- 3. inactive columns reject everything and pass nothing on (RICHARDS and KINEMATIC) -----------------------
  {
    vz_strat S=One(Mat(0.35,4,0.3,0.5,0.2)); vz_column c; double rej;
    double q=Step(c,S,1.0,0.01,rej); check(q==0.0 && rej==0.01,"inactive Step rejects",rej,0.01);
    q=Step(c,S,1.0,-0.01,rej); check(q==0.0 && rej==-0.01,"inactive Step rejects an upward demand",rej,-0.01);
    q=StepKinematic(c,S,2.0,0.01,rej); check(q==0.0 && rej==0.02,"inactive StepKinematic rejects",rej,0.02);
  }

  //-- 4. mass balance, bounds, sign rules over random fluxes, steps, materials and layering -------------------
  {
    SetReference(1);
    std::mt19937 g(12345); std::uniform_real_distribution<double> U(0.0,1.0);
    double worst=0,worstb=0; int nrun=0,bad=0,badb=0,badq=0,badr=0,badf=0;
    for (int run=0;run<400;run++){
      const int nl=1+run%3;
      vz_strat S; double zt=1e9; std::vector<double> zi={4.0-U(g)*2,1.5-U(g)};
      for (int l=0;l<nl;l++){
        double ths=0.25+0.25*U(g),Sy=(run%37==0)?0.0:std::min(ths,0.02+0.3*U(g)),b=2+8*U(g),Ks=std::pow(10.0,-3+3.5*U(g));
        S.ztop.push_back(zt); zt=(l<nl-1)?zi[l]:-1e9; S.zbot.push_back(zt); S.mat.push_back(Mat(ths,b,0.1+0.4*U(g),Ks,Sy));
      }
      vz_column c; Build(c,S,5.0+U(g),0.0,3+(int)(30*U(g)));
      for (size_t i=0;i<c.th.size();i++){const vz_mat &m=S.mat[c.im[i]]; c.th[i]=thr(m)+(m.ths-thr(m))*U(g)*U(g); c.psi[i]=PsiOf(m,c.th[i]);}
      SetAccuracy(run%2?0.02:0.005);
      for (int k=0;k<40;k++){
        double qt; const double u=U(g);
        if (u<0.15){qt=0;} else if (u<0.25){qt=-0.01*U(g);} else if (u<0.4){qt=3.0*U(g);} else {qt=0.05*U(g);}
        const double dt=std::pow(10.0,-2+3*U(g)),S0=Storage(c);
        double rej; vz_step_info inf; std::vector<double> o=c.th;
        const double qb=StepKinematic(c,S,dt,qt,rej,&inf); nrun++;
        const double err=std::fabs(Storage(c)-S0-(qt*dt-rej-qb*dt))/std::max(1e-3,std::fabs(qt*dt)+qb*dt);
        worst=std::max(worst,err); if (err>1e-12){bad++;}
        for (size_t i=0;i<c.th.size();i++){
          const vz_mat &m=S.mat[c.im[i]];
          const double lo=std::min(o[i],thr(m)),d=std::max(c.th[i]-m.ths,lo-c.th[i]);
          worstb=std::max(worstb,d); if (d>1e-13){badb++;}
        }
        if (qb<0.0){badq++;}
        if ((qt>=0 && (rej<-1e-15 || rej>qt*dt*(1+1e-12))) || (qt<0 && rej!=qt*dt)){badr++;}
        if (!finite_all(c) || !std::isfinite(qb)){badf++;}
      }
    }
    printf("random: %d steps, worst relative mass error %.2g, worst bound violation %.2g\n",nrun,worst,worstb);
    check(bad==0,"KW mass exact (random)",worst,1e-12);
    check(badb==0,"KW contents within [min(th0,ths-Sy), ths] (random)",worstb,0);
    check(badq==0,"KW qbot >= 0 (random)",badq,0);
    check(badr==0,"KW rejection rules (random)",badr,0);
    check(badf==0,"KW finite (random, incl. SPEC_YIELD 0)",badf,0);
    SetAccuracy(0.02);
  }

  //-- 5. monotonicity: more inflow never gives less water anywhere nor less outflow -----------------------------
  {
    SetReference(1);
    vz_strat S=Two(Mat(0.35,4,0.3,0.8,0.2),Mat(0.42,7,0.5,0.03,0.06),2.5);
    int bad=0;
    for (int run=0;run<50;run++){
      vz_column a; Build(a,S,5.0,0.0,16);
      double rej; for (int k=0;k<run%7;k++){StepKinematic(a,S,1.0,0.05,rej);}
      vz_column b=a; double qa=0,qb2=0;
      for (int k=0;k<10;k++){
        const double q1=0.002*(run+1)*(k%3),q2=q1*1.3+0.001;
        qa+=StepKinematic(a,S,0.7,q1,rej); qb2+=StepKinematic(b,S,0.7,q2,rej);
        for (size_t i=0;i<a.th.size();i++){if (b.th[i]<a.th[i]-1e-12){bad++;}}
        if (qb2<qa-1e-12){bad++;}
      }
    }
    check(bad==0,"KW monotone in the inflow",bad,0);
  }

  //-- 6. analytical kinematic wave: front arrival (shock speed q/(th_q - thr)) and drainage tail, grid refinement
  {
    SetReference(1);
    const vz_mat m=Mat(0.35,4,0.3,0.5,0.2); const kwa W(m); vz_strat S=One(m);
    const double L=6.0,q=0.01,ta=L*(W.thq(q)-W.thr)/q,ts=ta+60.0;
    printf("K1 analytic: L %.0f m, q %.0f mm/d, th_q %.4f, residual %.2f, arrival at %.2f d, input stops at %.2f d\n",L,q*1000,W.thq(q),W.thr,ta,ts);
    double prevA=1e9,prevT=1e9; int nconv=0;
    const int Ns[4]={16,32,64,128}; double eA[4],eT[4];
    for (int r=0;r<4;r++){
      const int N=Ns[r]; const double dt=0.05*16.0/N;
      SetAccuracy(0.02*16.0/N);
      vz_column c; Build(c,S,L,0.0,N);
      double t=0,t50=-1,rej; double eTail=0; int nt=0;
      const double tend=ts+300.0;
      while (t<tend-1e-9){
        const double qt=(t<ts-1e-9)?q:0.0, qb=StepKinematic(c,S,dt,qt,rej); t+=dt;
        if ((t50<0) && (qb>=0.5*q)){t50=t-0.5*dt;}
        if (t>ts+0.5*dt){ //tail: qbot(t) = K(th) with c(th) = L/(t - ts) once t - ts > L/c(th_q); the step-mean of K
          const double tm=t-0.5*dt-ts,cq=W.c(W.thq(q));
          const double qa=(tm<L/cq)?q:W.K(W.thc(L/tm));
          if (tm>1.5*L/cq){eTail=std::max(eTail,std::fabs(qb-qa)/q); nt++;}
        }
      }
      eA[r]=std::fabs(t50-ta)/ta; eT[r]=eTail;
      printf("K1 N=%3d dt=%.4f d: arrival (half the flux) %.3f d, error %.2f %%; tail max error %.2f %% of q\n",N,dt,t50,eA[r]*100,eT[r]*100);
      if ((eA[r]<prevA) && (eT[r]<prevT)){nconv++;}
      prevA=eA[r]; prevT=eT[r];
    }
    check(nconv==4,"K1 front and tail errors fall with refinement",nconv,4);
    check(eA[0]<0.05,"K1 front arrival within 5 % at N=16",eA[0],0.05);
    check(eA[3]<0.01,"K1 front arrival within 1 % at N=128",eA[3],0.01);
    check(eT[3]<0.02,"K1 drainage tail within 2 % of q at N=128",eT[3],0.02);
    SetAccuracy(0.02);
    //the default grid and accuracy with daily steps (what the coupled runs use)
    vz_column c; Build(c,S,L,0.0,16); double t=0,t50=-1,rej;
    while (t<ta*2){double qb=StepKinematic(c,S,1.0,q,rej); t+=1.0; if ((t50<0) && (qb>=0.5*q)){t50=t-0.5;}}
    printf("K1 default (N=16, accuracy 0.02, daily steps): arrival %.2f d vs %.2f d (%.1f %%)\n",t50,ta,100*(t50-ta)/ta);
    check(std::fabs(t50-ta)/ta<0.1,"K1 default arrival within 10 %",t50,ta);
  }

  //-- 7. sand over clay: the clay limits the flux, water backs up to saturation, then the top rejects ----------
  {
    SetReference(1);
    const vz_mat sand=Mat(0.35,4,0.2,1.0,0.25),clay=Mat(0.45,10,0.5,0.004,0.05);
    vz_strat S=Two(sand,clay,2.0); vz_column c; Build(c,S,5.0,0.0,16);
    const double q=0.05; double rej,qb=0,maxth=0,R=0,In=0,Out=0; const double S0=Storage(c);
    for (int d=0;d<2000;d++){
      qb=StepKinematic(c,S,1.0,q,rej); R+=rej; In+=q; Out+=qb;
      for (size_t i=0;i<c.th.size();i++){maxth=std::max(maxth,c.th[i]-S.mat[c.im[i]].ths);}
    }
    bool sat=true; size_t iclay=0; while (c.im[iclay]==0){iclay++;}
    for (size_t i=0;i<=iclay;i++){sat&=(c.th[i]>=S.mat[c.im[i]].ths-1e-9);}
    printf("sand over clay: flux to the water table %.5f m/d (clay Ks %.3f), rejected %.5f m/d at the end, %.1f m rejected in all\n",qb,clay.Ks,rej,R);
    check(std::fabs(qb-clay.Ks)<1e-6,"sand over clay: steady flux = clay Ks",qb,clay.Ks);
    check(std::fabs(rej-(q-clay.Ks))<1e-6,"sand over clay: the top rejects the rest",rej,q-clay.Ks);
    check(sat,"sand over clay: sand and top clay node saturated",sat,1);
    check(maxth<=1e-15,"sand over clay: no content above ths",maxth,0);
    check(std::fabs(Storage(c)-S0-(In-R-Out))<1e-10,"sand over clay: mass exact",Storage(c)-S0,In-R-Out);
  }

  //-- 8. SPEC_YIELD 0 and POROSITY guards ------------------------------------------------
  {
    SetReference(1);
    vz_mat m0=Mat(0.3,4,0.3,0.5,0.0); vz_strat S=One(m0); vz_column c; Build(c,S,6.0,0.0,16);
    bool ths=true; for (double t:c.th){ths&=(t==0.3);} check(ths,"Sy 0: column at ths",c.th[0],0.3);
    double f=InitSteadyKinematic(c,S,0.002); check(finite_all(c) && f==0.002,"Sy 0: steady start finite",f,0.002);
    double rej,S0=Storage(c),qb=StepKinematic(c,S,1.0,0.002,rej);
    check(finite_all(c) && std::fabs(qb-0.002)<1e-15 && std::fabs(Storage(c)-S0)<1e-15,"Sy 0: passes the inflow through",qb,0.002);
    qb=StepKinematic(c,S,1.0,0.8,rej); check(std::fabs(qb-0.5)<1e-15 && std::fabs(rej-0.3)<1e-15,"Sy 0: passes Ks, rejects the rest",qb,0.5);
    vz_mat mp=Mat(0.0,4,0.3,0.5,0.0); vz_strat Sp=One(mp); vz_column cp; Build(cp,Sp,3.0,0.0,8);
    qb=StepKinematic(cp,Sp,1.0,0.01,rej); check(finite_all(cp) && std::isfinite(qb) && std::fabs(qb+rej-0.01)<1e-15,"POROSITY 0: finite, nothing stored",qb,0.01);
    check(std::isfinite(KofKinematic(m0,0.3)) && KofKinematic(m0,0.3)==0.5 && KofKinematic(m0,0.2)==0.0,"Sy 0: K finite",KofKinematic(m0,0.3),0.5);
    vz_mat mt=Mat(0.3,4,0.3,0.5,1e-300); check(std::isfinite(KofKinematic(mt,0.3)),"tiny Sy: K finite",KofKinematic(mt,0.3),0.5);
  }

  //-- 9. steady start (InitSteadyKinematic): K(th) = q per node, steady under the step; backed-up when q > a deeper Ks
  {
    SetReference(1);
    const vz_mat a=Mat(0.35,4,0.3,0.5,0.2),b=Mat(0.40,6,0.4,0.02,0.08);
    for (int cs=0;cs<3;cs++){
      vz_strat S=(cs==0)?One(a):Two(a,b,2.5); const double q=(cs==2)?0.05:0.004;
      vz_column c; Build(c,S,5.0,0.0,16);
      const double f=InitSteadyKinematic(c,S,q),fw=(cs==2)?b.Ks:q;
      check(std::fabs(f-fw)<1e-18,"steady start flux",f,fw);
      double kmax=0; for (size_t i=0;i<c.th.size();i++){const double k=KofKinematic(S.mat[c.im[i]],c.th[i]); if (c.th[i]<S.mat[c.im[i]].ths){kmax=std::max(kmax,std::fabs(k-f)/f);}}
      check(kmax<1e-12,"steady start K(th) = q",kmax,0);
      const std::vector<double> o=c.th; double rej,qb=0,rj=0;
      for (int d=0;d<30;d++){qb=StepKinematic(c,S,1.0,q,rej); rj=rej;}
      double dmax=0; for (size_t i=0;i<o.size();i++){dmax=std::max(dmax,std::fabs(c.th[i]-o[i]));}
      printf("steady start case %d: q %.3f, flux %.3f, largest content change after 30 days %.2g\n",cs,q,qb,dmax);
      check(dmax<1e-12,"steady start stays steady",dmax,0);
      check(std::fabs(qb-f)<1e-12*std::max(f,1e-3) && std::fabs(rj-(q-f))<1e-12,"steady start: flux and rejection",qb,f);
    }
  }

  //-- 10. speed: one 16-node column step (daily step, recharge in transit) ---------------------------------------
  {
    SetReference(1);
    vz_strat S=One(Mat(0.35,4,0.3,0.5,0.2)); vz_column c; Build(c,S,6.0,0.0,16);
    double rej; std::vector<double> qs; for (int k=0;k<100;k++){qs.push_back((k%30<3)?0.04:0.0);}
    int sub=0; vz_step_info inf;
    auto t0=std::chrono::steady_clock::now(); const int R=200;
    for (int r=0;r<R;r++){for (int k=0;k<100;k++){StepKinematic(c,S,1.0,qs[k],rej,&inf); sub+=inf.substeps;}}
    const double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/(R*100);
    SetReference(0); vz_column cr; Build(cr,S,6.0,0.0,16);
    t0=std::chrono::steady_clock::now();
    for (int r=0;r<R/4;r++){for (int k=0;k<100;k++){Step(cr,S,1.0,qs[k],rej,&inf);}}
    const double usr=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/(R/4*100);
    printf("speed: KINEMATIC %.1f us per 16-node column step (%.1f substeps), RICHARDS %.1f us\n",us,(double)sub/(R*100),usr);
  }

  printf("kinematic unit tests: %d checks, %d failed\n",ncheck,nfail);
  return nfail?1:0;
}
