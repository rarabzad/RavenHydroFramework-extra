// Unit tests of the unsaturated column (GWVadose.cpp): retention, steady infiltration against an independent ODE
// integration, mass conservation, perched water, moving water table, capillary rise, speed.
// Build: g++ -O2 -std=c++11 -I<src> vadose_unit.cpp <src>/GWVadose.cpp -o vadose_unit
// With an argument (a file name) it also writes the bottom-flux series of the drainage case for vadose_ref.py.
#include "GWVadose.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <chrono>
#include <algorithm>
using namespace gwvz;
static int nfail=0,ncheck=0;
static void check(bool ok,const char *what,double got=0,double want=0)
{
  ncheck++; if (!ok){nfail++; printf("  FAIL %s (got %.6g, want %.6g)\n",what,got,want);}
}
static vz_mat Mat(double ths,double b,double psia,double Ks,double Sy){vz_mat m; m.ths=ths; m.b=b; m.psia=psia; m.Ks=Ks; m.Sy=Sy; m.Ss=1e-5; return m;}
static vz_strat One(const vz_mat &m){vz_strat s; s.ztop.push_back(1e9); s.zbot.push_back(-1e9); s.mat.push_back(m); return s;}

// steady downward flux q through a column above a water table at z=0: dpsi/dz = q/K(psi) - 1, psi(0) = 0 (z upward),
// integrated with RK4 on a fine grid (independent of the finite-volume solver)
static double SteadyPsi(const vz_strat &S,double q,double z)
{
  int n=20000; double h=z/n,psi=0.0,zz=0.0;
  auto f=[&](double zq,double p){const vz_mat &m=S.mat[std::max(S.Find(zq),0)]; double K=Kof(m,p); return q/std::max(K,1e-30)-1.0;};
  for (int i=0;i<n;i++){
    double k1=f(zz,psi),k2=f(zz+0.5*h,psi+0.5*h*k1),k3=f(zz+0.5*h,psi+0.5*h*k2),k4=f(zz+h,psi+h*k3);
    psi+=h*(k1+2*k2+2*k3+k4)/6.0; zz+=h;
  }
  return psi;
}

int main(int argc,char **argv)
{
  if (argc>2){SetAccuracy(atof(argv[2]));}
  //-- retention and conductivity: continuity at the Hutson-Cass junction, derivatives against finite differences
  {
    vz_mat m=Mat(0.4,5.0,0.3,1.0,0.25); int bad=0,badk=0,badi=0;
    for (double psi=-50.0;psi<0.5;psi+=0.0137){
      double d,dk; Theta(m,psi,&d); Kof(m,psi,&dk); double e=1e-7;
      double fd=(Theta(m,psi+e)-Theta(m,psi-e))/(2*e),fk=(Kof(m,psi+e)-Kof(m,psi-e))/(2*e);
      if (std::fabs(fd-d)>1e-4*std::max(1.0,std::fabs(d))){bad++;}
      if (std::fabs(fk-dk)>1e-4*std::max(1.0,std::fabs(dk))){badk++;}
      if ((psi<0.0) && std::fabs(PsiOf(m,Theta(m,psi))-psi)>1e-8*std::max(1.0,std::fabs(psi))){badi++;}
    }
    check(bad==0,"d theta/d psi matches finite differences (incl. the Hutson-Cass junction)",bad,0);
    check(badk==0,"dK/d psi matches finite differences",badk,0);
    check(badi==0,"PsiOf inverts Theta",badi,0);
    double Si=2*m.b/(1+2*m.b),si=m.psia*std::pow(Si,-m.b);
    check(std::fabs(Theta(m,-si*(1+1e-9))-Theta(m,-si*(1-1e-9)))<1e-8,"retention continuous at the junction");
    check(std::fabs(Theta(m,0.0)-m.ths)<1e-14 && Kof(m,0.0)==m.Ks,"saturated at psi=0");
  }
  //-- steady infiltration: the column converges to the steady profile, bottom flux = top flux
  {
    vz_mat m=Mat(0.40,4.0,0.25,0.5,0.2); vz_strat S=One(m);
    vz_column c; Build(c,S,3.0,0.0,24);
    double q=0.02,rej,qb=0.0;
    for (int d=0;d<400;d++){qb=Step(c,S,1.0,q,rej);}
    check(std::fabs(qb-q)<1e-6*q,"steady infiltration: bottom flux equals top flux",qb,q);
    double emax=0.0;
    for (size_t i=0;i<c.zc.size();i++){double ps=SteadyPsi(S,q,c.zc[i]); emax=std::max(emax,std::fabs(c.psi[i]-ps));}
    check(emax<0.02,"steady profile within 2 cm of the RK4 integration (24 nodes over 3 m)",emax,0.02);
  }
  //-- mass: inflow - outflow - storage change = 0 over a wet-dry sequence, and the rejection when the top saturates
  {
    vz_mat m=Mat(0.35,6.0,0.4,0.05,0.15); vz_strat S=One(m);
    vz_column c; Build(c,S,5.0,0.0,16);
    double S0=Storage(c),in=0,out=0,rej=0,worst=0;
    for (int d=0;d<200;d++){
      double q=(d%20<3)?0.5:0.0; double r; double qb=Step(c,S,1.0,q,r);  //0.5 m/d > Ks: part is rejected
      in+=q-r; out+=qb; rej+=r;
      worst=std::max(worst,std::fabs(S0+in-out-Storage(c)));
    }
    check(worst<1e-10,"mass conserved over 200 days with storms beyond Ks",worst,0);
    check(rej>0.0,"inflow beyond the saturated top is rejected",rej,0);
  }
  //-- perched water: a low-conductivity layer under a permeable one holds a saturated zone above it
  {
    vz_strat S; S.ztop={1e9,2.0}; S.zbot={2.0,-1e9}; S.mat={Mat(0.40,4.0,0.2,1.0,0.25),Mat(0.45,10.0,0.5,0.002,0.05)};
    vz_column c; Build(c,S,4.0,0.0,30);
    double rej,qb=0; for (int d=0;d<600;d++){qb=Step(c,S,1.0,0.01,rej);}
    double pmax=-1e9; for (size_t i=0;i<c.zc.size();i++){if (c.zc[i]>2.0){pmax=std::max(pmax,c.psi[i]);}}
    check(pmax>0.0,"perched saturated zone above the low-K layer (psi > 0)",pmax,0);
    check(std::fabs(qb-0.01+rej)<1e-4,"steady perched flow: bottom flux = accepted inflow",qb,0.01-rej);
  }
  //-- moving water table: absorbed water = relative storage change; falling table opens cells at the reference
  {
    vz_mat m=Mat(0.40,4.0,0.25,0.5,0.2); vz_strat S=One(m);
    vz_column c; Build(c,S,3.0,0.0,16); double r; for (int d=0;d<5;d++){Step(c,S,1.0,0.05,r);}
    double R0=RelStorage(c,S); double ab=MoveBottom(c,S,1.0,16); double R1=RelStorage(c,S);
    check(std::fabs(R0-ab-R1)<1e-12,"rising table: relative storage = absorbed + what stays",R0-ab-R1,0);
    double R2=RelStorage(c,S); double ab2=MoveBottom(c,S,-0.5,16); double R3=RelStorage(c,S);
    check(std::fabs(ab2)<1e-15 && std::fabs(R3-R2)<1e-12,"falling table: nothing absorbed, relative storage kept",R3-R2,0);
    double R4=RelStorage(c,S); double ab3=MoveBottom(c,S,3.5,16);
    check(!c.active && std::fabs(ab3-R4)<1e-12,"table above the column: all relative water absorbed, column gone",ab3,R4);
  }
  //-- capillary rise: a dry soil layer above a shallow column draws water up; none into a soil wetter than hydrostatic
  {
    vz_mat m=Mat(0.40,4.0,0.25,0.5,0.2); vz_strat S=One(m);
    vz_column c; Build(c,S,0.6,0.0,12);
    double up=CapRise(c,0.1,0.3,5.0,10.0,0.1);      //soil suction 10 m
    check(up>0.0,"capillary rise into a dry soil above a shallow water table",up,0);
    double dn=CapRise(c,0.1,0.3,5.0,0.3,0.1);       //soil suction 0.3 m, less than hydrostatic (0.7 m): none
    check(dn==0.0,"no capillary rise into a soil wetter than hydrostatic",dn,0);
    //exact steady flux against values from scipy (quad + brentq, dimensionless Q = q/Ks)
    check(std::fabs(RiseExact(1,1,5,5,10)/0.02072-1)<1e-3,"exact rise b=5 d/psia=5 psis/psia=10",RiseExact(1,1,5,5,10),0.02072);
    check(std::fabs(RiseExact(1,1,10,20,24)/0.0005271-1)<1e-3,"exact rise b=10 d/psia=20 psis/psia=24",RiseExact(1,1,10,20,24),0.0005271);
    check(std::fabs(RiseExact(0.2,0.2,5,1,-1)/0.00587-1)<1e-3,"exact rise to an infinitely dry point",RiseExact(0.2,0.2,5,1,-1),0.00587);
    check(RiseExact(1,1,5,5,4.9)==0.0,"no rise to a point wetter than hydrostatic");
    check(std::fabs(RiseExact(1,1,5,0.5,0.8)-(0.8/0.5-1))<1e-12,"saturated throughout: Darcy",RiseExact(1,1,5,0.5,0.8),0.6);
    check(Rise(0.5,0.25,4.0,3.0,-1)<Rise(0.5,0.25,4.0,1.0,-1) && Rise(0.5,0.25,4.0,1.0,2.0)<Rise(0.5,0.25,4.0,1.0,20.0),
          "rise falls with depth and grows with the suction");
    //table against the direct solution
    double emax=0.0; srand(7);
    for (int k=0;k<4000;k++){
      static const double bb[5]={2.0,3.5,5.0,8.0,11.0}; double b=bb[k%5];
      double dz=std::exp(std::log(0.02)+(std::log(200.0)-std::log(0.02))*rand()/(double)RAND_MAX);
      double p1=(k%3==0)?0.0:std::exp(std::log(0.02)+(std::log(100.0)-std::log(0.02))*rand()/(double)RAND_MAX);
      double ps=(k%7==0)?-1:p1+dz*std::exp(12.0*rand()/(double)RAND_MAX);
      double a=RiseBetween(1,1,b,dz,p1,ps),e=RiseBetweenExact(1,1,b,dz,p1,ps);
      if (e>1e-12){emax=std::max(emax,std::fabs(a-e)/e);}
    }
    check(emax<0.025,"tabulated steady rise within 2.5% of the direct solution",emax,0.025);
    //the finite-volume column at steady upward flow reproduces the exact relation: with qtop = -RiseExact(d, psis) the
    //suction of the top node (d above the water table) settles at psis
    {
      vz_column c2; Build(c2,S,2.0,0.0,40); double r;
      const double d=c2.zc[0],psis=3.0,q=RiseExact(m.Ks,m.psia,m.b,d,psis);
      for (int it=0;it<3000;it++){Step(c2,S,1.0,-q,r);}
      check(std::fabs(-c2.psi[0]/psis-1)<0.03,"Richards column at steady rise: top suction equals the exact relation's (3%)",-c2.psi[0],psis);
    }
  }
  //-- robustness: remap across two materials, an air-dry column, inflow far above Ks, an upward demand
  //   the column cannot supply
  {
    vz_strat S; S.ztop={1e9,2.7}; S.zbot={2.7,-1e9}; S.mat={Mat(0.45,8.0,0.3,0.5,0.25),Mat(0.30,4.0,0.2,0.5,0.25)};
    S.mat[0].Ss=S.mat[1].Ss=1e-7;
    vz_column c; Build(c,S,4.0,0.0,16); double r,rejT=0,qbT=0; vz_step_info inf; int fails=0;
    for (int d=0;d<40;d++){Step(c,S,1.0,0.04,r);}
    MoveBottom(c,S,-0.09,16);
    double thmax=0; for (size_t i=0;i<c.th.size();i++){thmax=std::max(thmax,c.th[i]/S.mat[c.im[i]].ths);}
    for (int d=0;d<10;d++){double qb=Step(c,S,1.0,0.04,r,&inf); rejT+=r; qbT+=qb; fails+=inf.fails;}
    check(thmax<=1.0+1e-12,"remap across materials: no node above its porosity",thmax,1.0);
    check(qbT>0.3 && rejT<0.05,"remap across materials: the column keeps passing water",qbT,0.3);
    vz_mat m=Mat(0.30,15.0,0.3,0.1,0.29); vz_strat S1=One(m); vz_column d1; Build(d1,S1,5.0,0.0,16);
    for (size_t i=0;i<d1.th.size();i++){d1.psi[i]=-1e5; d1.th[i]=Theta(m,d1.psi[i]);}
    double rj=0,in=0; for (int d=0;d<10;d++){Step(d1,S1,1.0,0.02,r); rj+=r; in+=0.02;}
    check(rj<1e-6,"an air-dry column takes the inflow",rj,0);
    vz_mat m2=Mat(0.35,6.0,0.4,0.001,0.15); vz_strat S2=One(m2); vz_column w; Build(w,S2,5.0,0.0,16); int sub=0;
    for (int d=0;d<5;d++){double S0=Storage(w); double qb=Step(w,S2,1.0,0.1,r,&inf); sub+=inf.substeps;
      check(std::fabs(S0+(0.1-r)-qb-Storage(w))<1e-9,"inflow far above Ks: mass exact",S0+(0.1-r)-qb-Storage(w),0);}
    check(sub<5000,"inflow far above Ks: few substeps (saturated top first)",sub,5000);
    vz_column u; Build(u,S1,0.5,0.0,8); double S0=Storage(u); double qb=Step(u,S1,1.0,-0.2,r);
    check(r<0.0 && std::fabs(S0+(-0.2-r)-qb-Storage(u))<1e-9,"upward demand beyond supply: shortfall returned (rejected < 0), mass exact",r,0);
  }
  //-- drainage of a wet column to a water table (series for vadose_ref.py) and speed
  {
    vz_mat m=Mat(0.40,4.0,0.25,0.5,0.2); vz_strat S=One(m);
    vz_column c; Build(c,S,4.0,0.0,16);
    for (size_t i=0;i<c.th.size();i++){c.th[i]=0.38; c.psi[i]=PsiOf(m,c.th[i]);}
    FILE *f=(argc>1)?fopen(argv[1],"w"):NULL;
    double rej,t=0; vz_step_info inf; int sub=0,newt=0;
    for (int d=0;d<60;d++){double qb=Step(c,S,0.5,0.0,rej,&inf); sub+=inf.substeps; newt+=inf.newton; t+=0.5; if (f){fprintf(f,"%.4f %.10e\n",t,qb);}}
    if (f){fclose(f);}
    printf("  drainage: %d substeps, %d Newton iterations over 60 half-days\n",sub,newt);
    //speed: 4300 columns of 16 nodes, one day with a pulse
    std::vector<vz_column> cols(4300); for (auto &cc:cols){Build(cc,S,3.0+0.0*1,0.0,16);}
    auto t0=std::chrono::steady_clock::now();
    for (int d=0;d<10;d++){for (auto &cc:cols){Step(cc,S,1.0,(d==2)?0.03:0.0,rej);}}
    double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
    printf("  speed: 4300 columns x 10 days in %.3f s (%.2f ms per day)\n",sec,100.0*sec);
    check(sec<20.0,"4300 columns x 10 days in under 20 s",sec,20);
  }
  printf("vadose unit tests: %d checks, %d failed\n",ncheck,nfail);
  return nfail?1:0;
}
