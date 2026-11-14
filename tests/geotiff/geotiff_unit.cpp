// Copyright (c) 2026 Rezgar Arabzadeh -- Raven-MODFLOW 6 groundwater coupling
// SPDX-License-Identifier: Artistic-2.0
// Unit driver for the GeoTIFF reader (GWGeoTIFF) and the rasters built on it (CGWRaster); run by geotiff_check.py.
// compile: g++ -std=c++11 -O2 -I$RAVEN_SRC/src geotiff_unit.cpp $RAVEN_SRC/src/GWGeoTIFF.cpp $RAVEN_SRC/src/GWGeometry.cpp -o geotiff_unit
//   geotiff_unit dump <file>                  georeferencing, CRS, encoding and every value (GWGeoTIFF::Read), or ERROR <message>
//   geotiff_unit raster <file> <crs|NONE>     CGWRaster::Read with :InputCRS <crs>: OK [note] or ERROR <message>
//   geotiff_unit samplecmp <a> <b> <crs|NONE> CGWRaster samples of two rasters at 4000 points (inside, at the edges and
//                                             outside): the number of points where they differ (value bits or found/not found)
//   geotiff_unit sample <file> <n>            CGWRaster samples (lon/lat) at n points over the raster's extent and 10% around it
//   geotiff_unit fuzz <seed> <n> <files...>   n damaged copies of each file (bytes changed, cut, inserted, random) read from
//                                             memory, and random input to each decoder; any return is fine, a crash is not
//   geotiff_unit epsg <codes...>              GWGeom::GeographicEPSG of each code
// A last argument METRES reads the rasters as METRES after the file name of :LandSurface does (dump, raster, samplecmp).
#include "GWGeoTIFF.h"
#include "GWGeometry.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdint.h>

static bool ReadFile(const char *f,std::vector<unsigned char> &d)
{
  std::ifstream in(f,std::ios::binary); if (!in){return false;}
  std::ostringstream s; s<<in.rdbuf(); std::string t=s.str(); d.assign(t.begin(),t.end()); return true;
}
static uint64_t rng_state=88172645463325252ULL;
static uint64_t Rand(){rng_state^=rng_state<<13; rng_state^=rng_state>>7; rng_state^=rng_state<<17; return rng_state;}

int main(int argc,char **argv)
{
  if (argc<2){printf("usage: see the header of geotiff_unit.cpp\n"); return 2;}
  bool metres=false; if ((argc>2) && !strcmp(argv[argc-1],"METRES")){metres=true; argc--;} //(METRES after the file name of the .rvg)
  std::string mode=argv[1];
  if ((mode=="dump") && (argc>=3)){
    gw_geotiff R; std::string err;
    if (!GWGeoTIFF::Read(argv[2],R,err,metres)){printf("ERROR %s\n",err.c_str()); return 0;}
    printf("OK %d %d %.17g %.17g %.17g %.17g %d %.17g %d %d %d %d\n",R.ncols,R.nrows,R.xll,R.yll,R.dx,R.dy,R.hasNodata?1:0,R.nodata,
           R.epsg,R.geographic?1:0,R.rasterType,R.modelType);
    printf("FORMAT %s\n",R.format.c_str());
    for (int r=0;r<R.nrows;r++){
      for (int c=0;c<R.ncols;c++){printf(c?" %.17g":"%.17g",R.v[(size_t)r*R.ncols+c]);}
      printf("\n");
    }
    return 0;
  }
  if ((mode=="raster") && (argc>=4)){
    CGWCRS K; std::string err; const CGWCRS *pk=NULL;
    if (strcmp(argv[3],"NONE")){if (!K.Parse(argv[3],err)){printf("ERROR (crs) %s\n",err.c_str()); return 0;} pk=&K;}
    CGWRaster R; R.SetCRS(pk); R.SetMetres(metres);
    if (!R.Read(argv[2],err)){printf("ERROR %s\n",err.c_str()); return 0;}
    printf("OK %s\n",R.Note().c_str());
    return 0;
  }
  if ((mode=="samplecmp") && (argc>=5)){
    CGWCRS K; std::string err; const CGWCRS *pk=NULL;
    if (strcmp(argv[4],"NONE")){if (!K.Parse(argv[4],err)){printf("ERROR (crs) %s\n",err.c_str()); return 0;} pk=&K;}
    CGWRaster A,B; A.SetCRS(pk); B.SetCRS(pk); A.SetMetres(metres); B.SetMetres(metres);
    if (!A.Read(argv[2],err)){printf("ERROR %s\n",err.c_str()); return 0;}
    if (!B.Read(argv[3],err)){printf("ERROR %s\n",err.c_str()); return 0;}
    double e[4]; A.Extent(e);
    int ndiff=0,nfound=0,n=0;
    for (int i=0;i<4000;i++){
      double fx=-0.1+1.2*(double)(Rand()%100000)/100000.0,fy=-0.1+1.2*(double)(Rand()%100000)/100000.0;
      if (i<400){fx=(i%20)/19.0; fy=(i/20)/19.0;}                               //(a lattice through the edges and corners)
      double x=e[0]+fx*(e[2]-e[0]),y=e[1]+fy*(e[3]-e[1]),lon=x,lat=y,va=-1,vb=-1;
      if (pk!=NULL){pk->Inverse(x,y,lon,lat);}
      bool oa=A.Sample(lon,lat,va),ob=B.Sample(lon,lat,vb); n++;
      if (oa){nfound++;}
      if ((oa!=ob) || (oa && memcmp(&va,&vb,sizeof(double)))){ndiff++;}
    }
    printf("SAMPLES %d points, %d with values, %d differ\n",n,nfound,ndiff);
    return 0;
  }
  if ((mode=="sample") && (argc>=4)){
    CGWRaster A; std::string err;
    if (!A.Read(argv[2],err)){printf("ERROR %s\n",err.c_str()); return 0;}
    double e[4]; A.Extent(e); int n=atoi(argv[3]);
    for (int i=0;i<n;i++){
      double fx=-0.1+1.2*(double)(Rand()%100000)/100000.0,fy=-0.1+1.2*(double)(Rand()%100000)/100000.0,v=0;
      double x=e[0]+fx*(e[2]-e[0]),y=e[1]+fy*(e[3]-e[1]);
      bool ok=A.Sample(x,y,v);
      printf("%.17g %.17g %d %.17g\n",x,y,ok?1:0,ok?v:0.0);
    }
    return 0;
  }
  if ((mode=="fuzz") && (argc>=5)){
    rng_state^=(uint64_t)atoll(argv[2])*0x9E3779B97F4A7C15ULL; if (rng_state==0){rng_state=1;}
    int n=atoi(argv[3]),ncase=0,nok=0,nerr=0;
    for (int f=4;f<argc;f++){
      std::vector<unsigned char> d0; if (!ReadFile(argv[f],d0) || d0.empty()){printf("cannot read %s\n",argv[f]); return 1;}
      for (int k=0;k<n;k++){
        std::vector<unsigned char> d=d0; int kind=(int)(Rand()%5);
        if (kind==0){int m=1+(int)(Rand()%8); for (int j=0;j<m;j++){d[Rand()%d.size()]=(unsigned char)Rand();}}       //bytes changed anywhere
        else if (kind==1){size_t hd=std::min((size_t)512,d.size()); int m=1+(int)(Rand()%4); for (int j=0;j<m;j++){d[Rand()%hd]=(unsigned char)Rand();}} //in the header and directory
        else if (kind==2){d.resize(Rand()%d.size());}                                                              //cut
        else if (kind==3){size_t p=Rand()%d.size(); size_t m=1+Rand()%64; for (size_t j=0;j<m;j++){d.insert(d.begin()+p,(unsigned char)Rand());}} //bytes inserted
        else {size_t keep=8+Rand()%64; for (size_t j=std::min(keep,d.size());j<d.size();j++){d[j]=(unsigned char)Rand();}} //random after the header
        gw_geotiff R; std::string err;
        bool ok=GWGeoTIFF::ReadMemory(d.empty()?NULL:&d[0],d.size(),"fuzz",R,err);
        ncase++; if (ok){nok++; if ((int)R.v.size()!=R.ncols*R.nrows){printf("FUZZ inconsistent raster size\n"); return 1;}} else {nerr++; if (err.empty()){printf("FUZZ refused without a message\n"); return 1;}}
      }
    }
    //random input to the decoders
    int ndec=0;
    for (int k=0;k<3000;k++){
      std::vector<unsigned char> in(2+Rand()%400),out; for (size_t j=0;j<in.size();j++){in[j]=(unsigned char)Rand();}
      if (k%3==0){in[0]=0x78; in[1]=0x9c;}                                    //(a valid zlib header, so that DEFLATE blocks are decoded)
      if (k%3==1){in[0]=0x80;}                                                //(an LZW clear code first)
      bool full; std::string err; size_t lim=Rand()%5000;
      GWGeoTIFF::InflateZlib(&in[0],in.size(),out,lim,full,err); if (out.size()>lim){printf("FUZZ inflate wrote past its limit\n"); return 1;}
      GWGeoTIFF::LZWDecode  (&in[0],in.size(),out,lim,full,err); if (out.size()>lim){printf("FUZZ LZW wrote past its limit\n"); return 1;}
      GWGeoTIFF::PackBits   (&in[0],in.size(),out,lim,full,err); if (out.size()>lim){printf("FUZZ PackBits wrote past its limit\n"); return 1;}
      ndec++;
    }
    printf("FUZZ %d damaged files: %d read, %d refused with a message; %d random decoder inputs; no crash\n",ncase,nok,nerr,ndec);
    return 0;
  }
  if (mode=="epsg"){
    for (int i=2;i<argc;i++){printf("EPSG %s %s\n",argv[i],GWGeom::GeographicEPSG(atol(argv[i]))?"geographic":"not-geographic");}
    return 0;
  }
  printf("usage: see the header of geotiff_unit.cpp\n"); return 2;
}
