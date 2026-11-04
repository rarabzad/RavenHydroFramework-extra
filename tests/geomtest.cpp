// Copyright (c) 2026 Rezgar Arabzadeh -- Raven-MODFLOW 6 groundwater coupling
// SPDX-License-Identifier: Artistic-2.0
// Unit test harness for GWGeometry: clipping areas, projection, raster sampling
#include "GWGeometry.h"   // compile: g++ -std=c++11 -O2 -I$RAVEN_SRC/src geomtest.cpp $RAVEN_SRC/src/GWGeometry.cpp -o geomtest; then python3 geomtest_check.py
#include <cstdio>
#include <cmath>
#include <cstdlib>
int main(){
  srand(12345);
  FILE *f=fopen("clip.txt","w");
  for (int t=0;t<400;t++){               // random star-shaped (often concave) polygons, some with a hole
    int n=5+rand()%12; double cx=rand()%1000/100.0, cy=rand()%1000/100.0;
    gw_ring r;
    for (int i=0;i<n;i++){double a=2*M_PI*i/n, rad=0.5+3.0*(rand()%1000)/1000.0; gw_pt p; p.x=cx+rad*cos(a); p.y=cy+rad*sin(a); r.push_back(p);}
    double x0=rand()%1000/100.0-1, y0=rand()%1000/100.0-1, w=0.3+rand()%500/100.0;
    double A=GWGeom::ClipRingAreaToRect(r,x0,y0,x0+w,y0+w);
    fprintf(f,"%d %.17g %.17g %.17g %.17g %.17g",n,x0,y0,x0+w,y0+w,A);
    for (int i=0;i<n;i++){fprintf(f," %.17g %.17g",r[i].x,r[i].y);} fprintf(f,"\n");
  }
  fclose(f);
  CGWProjection P; P.SetOrigin(59.0,-125.3);
  f=fopen("proj.txt","w");
  for (int t=0;t<300;t++){double lon=-129+8.0*(rand()%10000)/10000.0, lat=56+7.0*(rand()%10000)/10000.0,x,y,lo,la;
    P.Forward(lon,lat,x,y); P.Inverse(x,y,lo,la); fprintf(f,"%.10f %.10f %.6f %.6f %.12f %.12f\n",lon,lat,x,y,lo,la);}
  fclose(f);
  CGWRaster R; std::string err; if (!R.Read("test.asc",err)){printf("raster read failed: %s\n",err.c_str()); return 1;}
  f=fopen("raster.txt","w");
  for (int t=0;t<200;t++){double lon=-2+4.0*(rand()%10000)/10000.0, lat=10+3.0*(rand()%10000)/10000.0,v=-1; bool ok=R.Sample(lon,lat,v); fprintf(f,"%.8f %.8f %d %.10f\n",lon,lat,ok?1:0,v);}
  fclose(f);
  // :InputCRS: a raster and GeoJSON files in UTM zone 10 (EPSG:32610), written by geomtest_check.py
  CGWCRS U,U9; if (!U.Parse("EPSG:32610",err) || !U9.Parse("EPSG:32609",err)){printf("CRS parse failed: %s\n",err.c_str()); return 1;}
  CGWRaster RU; RU.SetCRS(&U); if (!RU.Read("test_utm.asc",err)){printf("projected raster read failed: %s\n",err.c_str()); return 1;}
  f=fopen("raster_utm.txt","w");
  for (int t=0;t<300;t++){double lon=-123.5+1.0*(rand()%10000)/10000.0, lat=49.2+0.6*(rand()%10000)/10000.0,v=-1; bool ok=RU.Sample(lon,lat,v); fprintf(f,"%.10f %.10f %d %.10f\n",lon,lat,ok?1:0,v);}
  fclose(f);
  FILE *st=fopen("crs_status.txt","w");
  { CGWRaster RN; bool ok=RN.Read("test_utm.asc",err); fprintf(st,"raster_nocrs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_utm_poly.geojson","ID",sh,err,&U); fprintf(st,"poly_crs %d %s\n",ok?1:0,ok?"":err.c_str());
    FILE *g=fopen("poly_utm.txt","w");
    for (std::map<long long,std::vector<gw_ring> >::iterator it=sh.begin();it!=sh.end();it++){for (size_t r=0;r<it->second.size();r++){
      fprintf(g,"%lld %d %.17g",it->first,(int)r,GWGeom::SignedArea(it->second[r])); for (size_t n=0;n<it->second[r].size();n++){fprintf(g," %.14f %.14f",it->second[r][n].x,it->second[r][n].y);} fprintf(g,"\n");}}
    fclose(g); }
  { std::vector<gw_ring> L; std::vector<long long> id; bool ok=GWGeom::ReadGeoJSONLines("test_utm_line.geojson","",L,id,err,&U); fprintf(st,"line_crs %d %s\n",ok?1:0,ok?"":err.c_str());
    FILE *g=fopen("line_utm.txt","w"); for (size_t i=0;i<L.size();i++){for (size_t n=0;n<L[i].size();n++){fprintf(g,"%d %.14f %.14f\n",(int)i,L[i][n].x,L[i][n].y);}} fclose(g); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_utm_poly.geojson","ID",sh,err); fprintf(st,"poly_nocrs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::vector<gw_ring> L; std::vector<long long> id; bool ok=GWGeom::ReadGeoJSONLines("test_utm_line.geojson","",L,id,err); fprintf(st,"line_nocrs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_utm_poly.geojson","ID",sh,err,&U9); fprintf(st,"poly_mismatch %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_utm_bare.geojson","ID",sh,err); fprintf(st,"bare_nocrs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_utm_bare.geojson","ID",sh,err,&U); fprintf(st,"bare_crs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_ll_crs84.geojson","ID",sh,err); fprintf(st,"ll_nocrs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { std::map<long long,std::vector<gw_ring> > sh; bool ok=GWGeom::ReadGeoJSONPolygons("test_ll_crs84.geojson","ID",sh,err,&U); fprintf(st,"ll_crs %d %s\n",ok?1:0,ok?"":err.c_str()); }
  { CGWCRS T; bool ok=T.Parse("TMERC 0 -123 0.9996 500000 0 WGS84",err); fprintf(st,"same_tmerc %d \n",(ok && T.Same(U))?1:0);
    fprintf(st,"same_other %d \n",U.Same(U9)?1:0); }
  fclose(st);
  printf("done\n"); return 0;
}
