// Unit tests of :SoilZoneVadose LAG (GWVadoseLag.cpp, the linear storage cascade on the column of GWVadose.cpp):
// travel times (eq. lagtm), mass balance to round-off over random fluxes, steps, materials and layering, capacity
// (no content above ths), nodes below equilibrium, the inactive-column contract, tiny residence times (no int overflow),
// the steady start (InitSteadyLag), the Erlang response of equal reservoirs, the effective number of reservoirs of the
// column's grid, and speed. With an argument (a file name) it writes impulse responses of grid columns (one and two
// materials) for test_vz_lag.py, which compares them with the exact convolution of the exponentials.
// Build: g++ -O2 -std=c++11 -I<src> vadose_lag_unit.cpp <src>/GWVadose.cpp <src>/GWVadoseLag.cpp -o vadose_lag_unit
#include "GWVadose.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <chrono>
#include <random>
#include <algorithm>
using namespace gwvz;
static int nfail=0,ncheck=0;
static void check(bool ok,const char *what,double got=0,double want=0)
{
  ncheck++; if (!ok){nfail++; printf("  FAIL %s (got %.6g, want %.6g)\n",what,got,want);}
}
static vz_mat Mat(double ths,double b,double psia,double Ks,double Sy){vz_mat m; m.ths=ths; m.b=b; m.psia=psia; m.Ks=Ks; m.Sy=Sy; m.Ss=1e-5; return m;}
static vz_strat One(const vz_mat &m){vz_strat s; s.ztop.push_back(1e9); s.zbot.push_back(-1e9); s.mat.push_back(m); return s;}
static vz_strat Two(const vz_mat &a,const vz_mat &b,const double zi)
{
  vz_strat s; s.ztop.push_back(1e9); s.zbot.push_back(zi); s.mat.push_back(a);
  s.ztop.push_back(zi); s.zbot.push_back(-1e9); s.mat.push_back(b); return s;
}
static double Excess(const vz_column &c,const vz_strat &S,int i){return (c.th[i]-ThEq(S.mat[c.im[i]],c.zc[i]-c.zbot))*c.dz[i];}
static double Neff(const vz_column &c,const vz_strat &S,double par)
{
  double s=0,s2=0; for (size_t i=0;i<c.dz.size();i++){double k=LagTravelTime(S.mat[c.im[i]],par)*c.dz[i]; s+=k; s2+=k*k;} return s*s/s2;
}

int main(int argc,char **argv)
{
  const vz_mat sand=Mat(0.35,4.0,0.10,5.0,0.25),loam=Mat(0.43,5.4,0.30,0.25,0.15),clay=Mat(0.48,11.0,0.50,0.0002,0.05);
  //-- 1. travel time per metre (eq. lagtm): t_m = Sy Se_r/(eps q), Se_r = (q/Ks)^(1/eps), q = min(q_r, Ks)
  {
    const vz_mat M[3]={sand,loam,clay}; const char *nm[3]={"sand","loam","clay"};
    for (int j=0;j<3;j++){
      const vz_mat &m=M[j]; const double eps=2*m.b+3,q=std::min(0.001,m.Ks),want=m.Sy*std::pow(q/m.Ks,1/eps)/(eps*q);
      const double got=LagTravelTime(m,0.0);
      printf("  t_m %-5s Ks %-7g Sy %-5g b %-5g eps %-5g: %.4g d/m\n",nm[j],m.Ks,m.Sy,m.b,eps,got);
      check(std::fabs(got-want)<=1e-12*want,"t_m formula",got,want);
    }
    const double tc=LagTravelTime(clay,0.0),eps=2*clay.b+3;              //(clay: Ks below q_r, so Se_r = 1, t_m = Sy/(eps Ks))
    check(std::fabs(tc-clay.Sy/(eps*clay.Ks))<1e-12*tc,"t_m with Ks < q_r is Sy/(eps Ks)",tc,clay.Sy/(eps*clay.Ks));
    check(LagTravelTime(loam,4.0)==4.0,"t_m = parameter when > 0",LagTravelTime(loam,4.0),4.0);
    check(LagTravelTime(Mat(0.3,4,0.3,1,0.0),0.0)==0.0,"Sy 0: no residence time",LagTravelTime(Mat(0.3,4,0.3,1,0.0),0.0),0.0);
  }
  //-- 2. mass balance to round-off, capacity, qbot >= 0, finite: random columns, materials, layering, fluxes and steps
  {
    std::mt19937 rng(12345); std::uniform_real_distribution<double> U(0.0,1.0);
    double worst=0.0,over=0.0; int nonfin=0,negq=0,nst=0,ncol=0,nsub=0;
    for (int trial=0;trial<400;trial++){
      vz_mat a=Mat(0.30+0.2*U(rng),2.0+10.0*U(rng),0.05+0.5*U(rng),std::pow(10.0,-4.0+5.0*U(rng)),0.02+0.25*U(rng));
      vz_mat b=Mat(0.30+0.2*U(rng),2.0+10.0*U(rng),0.05+0.5*U(rng),std::pow(10.0,-4.0+5.0*U(rng)),0.02+0.25*U(rng));
      a.ths=std::max(a.ths,a.Sy+0.01); b.ths=std::max(b.ths,b.Sy+0.01);
      const double L=0.1+15.0*U(rng)*U(rng),zi=L*U(rng);
      const vz_strat S=(trial%3==0)?One(a):Two(a,b,zi);
      const int N=3+(int)(60*U(rng)); const double par=(trial%2)?0.0:std::pow(10.0,-3.0+4.5*U(rng));
      vz_column c; Build(c,S,L,0.0,N); ncol++;
      if (trial%5==0){ //a state written by another method: some nodes below equilibrium, some near saturation
        for (size_t i=0;i<c.th.size();i++){const vz_mat &m=S.mat[c.im[i]]; double r=U(rng); c.th[i]=(r<0.4)?std::max(Theta(m,-1e3),0.5*c.th[i]):(r<0.6)?m.ths:c.th[i]; c.psi[i]=PsiOf(m,c.th[i]);}
      }
      for (int st=0;st<40;st++){
        double r=U(rng),q=(r<0.3)?0.0:(r<0.4)?-0.01*U(rng):(r<0.5)?2.0*U(rng):0.05*U(rng)*U(rng);
        const double dt=(U(rng)<0.5)?1.0:std::pow(10.0,-2.0+2.7*U(rng));
        const double S0=Storage(c); double rej=0.0; vz_step_info inf;
        const double qb=StepLag(c,S,dt,q,rej,&inf,par);
        const double dS=Storage(c)-S0,res=dS-((q*dt-rej)-qb*dt);
        const double scale=std::fabs(q*dt)+std::fabs(qb*dt)+std::fabs(rej)+S0;          //(the flows and the storage summed)
        worst=std::max(worst,std::fabs(res)/scale); nst++; nsub+=inf.substeps;
        if (!std::isfinite(qb) || !std::isfinite(res)){nonfin++;}
        if (qb<0.0){negq++;}
        if ((q>=0.0) && (std::fabs(rej)>0.0)){nonfin++;}                   //(an active column takes any inflow)
        if ((q<0.0) && (std::fabs(rej-q*dt)>1e-15)){nonfin++;}             //(an upward demand is rejected entirely)
        for (size_t i=0;i<c.th.size();i++){over=std::max(over,c.th[i]-S.mat[c.im[i]].ths); if (!std::isfinite(c.th[i]) || !std::isfinite(c.psi[i])){nonfin++;}}
        if (st%9==8){MoveBottom(c,S,std::min(c.zbot+(U(rng)-0.5)*0.4*L,c.ztop-0.06),N);} //(the water table moves every ninth step)
      }
    }
    printf("  mass balance: %d columns, %d steps (%d substeps): worst residual %.3g of the step's flows and storage; largest content above ths %.3g\n",ncol,nst,nsub,worst,over);
    check(std::isfinite(worst) && (worst<1e-14),"mass balance to round-off",worst,1e-14);
    check(over<=1e-15,"no content above ths",over,0);
    check(nonfin==0,"finite results, rejection only for upward demands",nonfin,0);
    check(negq==0,"qbot >= 0",negq,0);
  }
  //-- 3. inactive column: qtop rejected, no qbot; an active column with an upward demand still drains
  {
    vz_strat S=One(loam); vz_column c; Build(c,S,0.0,1.0,16); double rej=0;
    double qb=StepLag(c,S,1.0,0.004,rej,0,0.0);
    check(!c.active && (qb==0.0) && (rej==0.004),"inactive column rejects qtop and returns no qbot",rej,0.004);
    qb=StepLag(c,S,1.0,-0.002,rej,0,0.0); check((qb==0.0) && (rej==-0.002),"inactive column rejects an upward demand",rej,-0.002);
    Build(c,S,5.0,0.0,16); c.th[0]+=0.05; c.psi[0]=PsiOf(loam,c.th[0]);
    const double S0=Storage(c); qb=StepLag(c,S,1.0,-0.003,rej,0,2.0);
    check((std::fabs(rej+0.003)<1e-18) && (qb>=0.0) && (std::fabs(Storage(c)-S0+qb)<1e-15),"upward demand rejected, the cascade drains",rej,-0.003);
  }
  //-- 4. nodes below equilibrium do not drain; inflow fills them
  {
    vz_strat S=One(sand); vz_column c; Build(c,S,4.0,0.0,16);
    for (size_t i=0;i<c.th.size();i++){c.th[i]-=0.02; c.psi[i]=PsiOf(sand,c.th[i]);}
    std::vector<double> th0=c.th; double rej=0;
    double qb=StepLag(c,S,10.0,0.0,rej,0,1.0);
    bool same=true; for (size_t i=0;i<c.th.size();i++){same&=(c.th[i]==th0[i]);}
    check(same && (qb==0.0),"a column below equilibrium without inflow does not move",qb,0);
    qb=StepLag(c,S,1.0,0.0004,rej,0,1.0);                                //(0.4 mm cannot fill the top node's 0.02 dz deficit)
    check((qb<1e-15) && (Excess(c,S,0)<0.0) && (std::fabs(c.th[0]-th0[0]-0.0004/c.dz[0])<1e-15),"inflow fills a node below equilibrium first",qb,0);
  }
  //-- 5. tiny residence times: N = 200 and LAG 1e-6 (the substep count overflowed an int)
  {
    vz_strat S=One(sand); vz_column c; Build(c,S,10.0,0.0,200); double rej=0; vz_step_info inf;
    const double S0=Storage(c); double qb=StepLag(c,S,1.0,0.01,rej,&inf,1e-6);
    check((int)c.th.size()==200,"200 nodes",(double)c.th.size(),200);
    check((inf.substeps>=1) && (inf.substeps<=50),"substeps clamped to [1, 50]",inf.substeps,50);
    check(std::isfinite(qb) && (std::fabs(qb-0.01)<=0.01*1e-5*10.0*1.01),"a near-zero residence time passes the inflow through (less q sum k)",qb,0.01);
    check(std::fabs(Storage(c)-S0-(0.01-qb))<1e-15,"mass with tiny k",Storage(c)-S0,0.01-qb);
    vz_column d; Build(d,S,10.0,0.0,200); qb=StepLag(d,S,1e-9,0.01,rej,&inf,1e-12);
    check(std::isfinite(qb) && (inf.substeps>=1) && (inf.substeps<=50),"dt/kmin of 1e3 .. 1e12",inf.substeps,50);
    vz_strat Z=One(Mat(0.3,4,0.3,1,0.0)); vz_column z; Build(z,Z,3.0,0.0,16);   //(Sy 0: residence time 0)
    qb=StepLag(z,Z,1.0,0.002,rej,&inf,0.0); check(std::isfinite(qb) && (inf.substeps==50),"Sy 0 (k = 0): finite",qb,0.002);
  }
  //-- 6. steady start: S_i = min(q k_i, Smax_i), then a step under q delivers q
  {
    const vz_strat S[3]={One(sand),Two(sand,loam,2.0),Two(loam,clay,1.5)}; const double qs[3]={0.0005,0.002,0.01};
    double worst=0.0,worstS=0.0;
    for (int j=0;j<3;j++){
      for (int iq=0;iq<3;iq++){
        vz_column c; Build(c,S[j],5.0,0.0,16); const double rel=InitSteadyLag(c,S[j],qs[iq],0.0);
        check(std::fabs(rel-RelStorage(c,S[j]))<1e-14,"InitSteadyLag returns the water above the reference",rel,RelStorage(c,S[j]));
        for (size_t i=0;i<c.th.size();i++){
          const vz_mat &m=S[j].mat[c.im[i]]; const double eq=ThEq(m,c.zc[i]-c.zbot);
          const double want=std::min(qs[iq]*LagTravelTime(m,0.0)*c.dz[i],(m.ths-eq)*c.dz[i]);
          worstS=std::max(worstS,std::fabs(Excess(c,S[j],(int)i)-want));
        }
        double rej=0; const double S0=Storage(c);
        const double qb=StepLag(c,S[j],1.0,qs[iq],rej,0,0.0);
        worst=std::max(worst,std::fabs(qb-qs[iq])/qs[iq]); worst=std::max(worst,std::fabs(Storage(c)-S0)/qs[iq]);
      }
    }
    printf("  steady start: S_i within %.2g m of min(q k_i, Smax_i); the next step delivers q within %.2g of q\n",worstS,worst);
    check(worstS<1e-15,"steady start contents",worstS,0);
    check(worst<1e-12,"steady start is steady",worst,1e-12);
    vz_column c; vz_strat S1=One(sand); Build(c,S1,0.0,1.0,16); check(InitSteadyLag(c,S1,0.001,0.0)==0.0,"steady start of an inactive column",0,0);
  }
  //-- 7. equal reservoirs: the response to water put in the top node is the Erlang density (k each, N nodes)
  {
    vz_strat S=One(sand); const int N=8; const double k=0.5,dz=0.25,V=0.004;   //(k = t_m dz with t_m = 2 d/m)
    vz_column c; c.ztop=N*dz; c.zbot=0.0; c.active=true;
    for (int i=0;i<N;i++){c.dz.push_back(dz); c.zc.push_back(c.ztop-(i+0.5)*dz); c.im.push_back(0);
      double th=ThEq(sand,c.zc[i]); c.th.push_back(th); c.psi.push_back(PsiOf(sand,th));}
    c.th[0]+=V/dz; c.psi[0]=PsiOf(sand,c.th[0]);
    double t=0.0,err=0.0,cum=0.0,mean=0.0; const double dt=0.25; double rej=0;
    for (int st=0;st<200;st++){
      const double qb=StepLag(c,S,dt,0.0,rej,0,2.0); cum+=qb*dt; t+=dt;
      double F=1.0,term=1.0; const double x=t/k; for (int j=1;j<N;j++){term*=x/j; F+=term;} F=1.0-std::exp(-x)*F;   //Erlang CDF
      err=std::max(err,std::fabs(cum/V-F)); mean+=(t-0.5*dt)*qb*dt/V;
    }
    printf("  Erlang (8 equal reservoirs, k = %.2g d, dt = %.2g d): largest difference of the cumulative response %.3g; mean %.4g d (exact %.4g)\n",k,dt,err,mean,N*k);
    check(err<1e-2,"Erlang response",err,1e-2);
    check(std::fabs(mean-N*k)<0.01*N*k,"mean travel time N k",mean,N*k);
  }
  //-- 8. effective number of reservoirs of the column grid (one material): manual table
  {
    const int Ns[10]={3,4,6,8,12,16,24,32,50,100}; const double want[10]={2.95,3.93,5.74,7.38,10.1,12.0,17.7,25.3,43.1,93.0};
    vz_strat S=One(loam); bool capped=true;
    printf("  N_eff:");
    for (int j=0;j<10;j++){
      vz_column c; Build(c,S,20.0,0.0,Ns[j]); const double ne=Neff(c,S,0.0);
      double dmin=1e9,dmax=0; for (size_t i=0;i<c.dz.size();i++){dmin=std::min(dmin,c.dz[i]); dmax=std::max(dmax,c.dz[i]);}
      if (Ns[j]>18){capped&=(dmax/dmin<std::pow(1.3,8)*1.000001);}
      printf(" %d:%.3g",Ns[j],ne);
      if (Ns[j]<=18 || capped){check(std::fabs(ne-want[j])<=0.0051*want[j]+0.005,"N_eff of the grid",ne,want[j]);}
    }
    printf("\n");
    if (!capped){printf("  SKIP N_eff for N > 18: the column grid (MakeGrid) is not capped at 1.3^8 (column library)\n");}
  }
  //-- 9. speed: 16-node column steps (daily, storm and drainage)
  {
    vz_strat S=Two(sand,loam,3.0); vz_column c; Build(c,S,6.0,0.0,16); double rej=0;
    const int n=200000; auto t0=std::chrono::high_resolution_clock::now(); double sum=0;
    for (int i=0;i<n;i++){const double q=((i%30)<3)?0.03:0.0; sum+=StepLag(c,S,1.0,q,rej,0,0.0);}
    const double us=std::chrono::duration<double,std::micro>(std::chrono::high_resolution_clock::now()-t0).count()/n;
    printf("  speed: %.2f us per 16-node column step (delivered %.4g m)\n",us,sum);
  }
  //-- impulse responses of grid columns for the exact convolution in test_vz_lag.py
  if (argc>1){
    FILE *f=fopen(argv[1],"w");
    struct Case {const char *name; vz_strat S; double L; int N; double par; double dt;};
    std::vector<Case> cs={{"one_material_N16",One(loam),6.0,16,2.0,0.25},{"one_material_N6",One(loam),6.0,6,4.0,0.5},
                          {"sand_over_loam_N16",Two(sand,loam,2.5),6.0,16,0.0,0.5},{"daily_N16",One(loam),6.0,16,2.0,1.0}};
    for (size_t j=0;j<cs.size();j++){
      const Case &C=cs[j]; vz_column c; Build(c,C.S,C.L,0.0,C.N);
      const double V=0.2*(C.S.mat[c.im[0]].ths-ThEq(C.S.mat[c.im[0]],c.zc[0]))*c.dz[0];   //(well inside the top node's room)
      c.th[0]+=V/c.dz[0]; c.psi[0]=PsiOf(C.S.mat[c.im[0]],c.th[0]);
      const int nst=(int)std::ceil(8.0*C.L*std::max(C.par,LagTravelTime(C.S.mat.back(),C.par))/C.dt)+40;
      fprintf(f,"CASE %s %zu %.17g %.17g %d\nK",C.name,c.dz.size(),C.dt,V,nst);
      for (size_t i=0;i<c.dz.size();i++){fprintf(f," %.17g",LagTravelTime(C.S.mat[c.im[i]],C.par)*c.dz[i]);}
      fprintf(f,"\nQ"); double rej=0;
      for (int st=0;st<nst;st++){fprintf(f," %.17g",StepLag(c,C.S,C.dt,0.0,rej,0,C.par)*C.dt);}
      fprintf(f,"\n");
    }
    fclose(f);
  }
  printf("LAG unit tests: %d checks, %d failed\n",ncheck,nfail);
  return nfail?1:0;
}
