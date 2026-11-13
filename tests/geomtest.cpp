// Copyright (c) 2026 Rezgar Arabzadeh -- Raven-MODFLOW 6 groundwater coupling
// SPDX-License-Identifier: Artistic-2.0
// Unit test harness for GWGeometry: clipping areas, projection, raster sampling
#include <sstream>
#include <fstream>
#include "GWGeometry.h"   // compile: g++ -std=c++11 -O2 -I$RAVEN_SRC/src geomtest.cpp $RAVEN_SRC/src/GWGeometry.cpp $RAVEN_SRC/src/GWGeoTIFF.cpp -o geomtest; then python3 geomtest_check.py
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
  //the no-data margin: points up to half a cell beyond the raster's edge (0.4 and 0.6 of a 0.5-degree cell west of it)
  f=fopen("raster_margin.txt","w");
  for (int t=0;t<2;t++){double lon=-3.0-((t==0)?0.4:0.6)*0.5,lat=11.25,v=-1; bool ok=R.Sample(lon,lat,v); fprintf(f,"%.8f %.8f %d %.10f\n",lon,lat,ok?1:0,v);}
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
  //"crs" members of GeoJSON files (crs_cases.txt, written by geomtest_check.py: name, file, :InputCRS spec or NONE)
  { std::ifstream C("crs_cases.txt"); std::string line;
    while (std::getline(C,line)){
      std::istringstream is(line); std::string name,file,spec,w; is>>name>>file; while (is>>w){spec+=(spec.empty()?"":" ")+w;}
      CGWCRS K; const CGWCRS *pk=NULL;
      if (spec!="NONE"){if (!K.Parse(spec,err)){fprintf(st,"%s 0 (spec) %s\n",name.c_str(),err.c_str()); continue;} pk=&K;}
      std::map<long long,std::vector<gw_ring> > sh; err=""; bool ok=GWGeom::ReadGeoJSONPolygons(file,"ID",sh,err,pk);
      fprintf(st,"%s %d %s\n",name.c_str(),ok?1:0,ok?"":err.c_str());
    }
  }
  fclose(st);
  //GeoJSON coordinates and members (json_cases.txt, written by geomtest_check.py: name, file, poly or line, ID field or -)
  { std::ifstream C("json_cases.txt"); std::string line; FILE *g=fopen("json_status.txt","w");
    while (std::getline(C,line)){
      std::istringstream is(line); std::string name,file,kind,idf; is>>name>>file>>kind>>idf; if (idf=="-"){idf="";}
      bool ok; err="";
      if (kind=="poly"){std::map<long long,std::vector<gw_ring> > sh; ok=GWGeom::ReadGeoJSONPolygons(file,idf,sh,err);}
      else {std::vector<gw_ring> L; std::vector<long long> id; ok=GWGeom::ReadGeoJSONLines(file,idf,L,id,err);}
      fprintf(g,"%s %d %s\n",name.c_str(),ok?1:0,ok?"":err.c_str());
    }
    fclose(g); }
  //conic projections (conic_cases.txt, written by geomtest_check.py: the parameters, then lon lat): forward and inverse
  { std::ifstream C("conic_cases.txt"); std::string line; FILE *g=fopen("conic.txt","w");
    while (std::getline(C,line)){
      const size_t b=line.find('|'); if (b==std::string::npos){continue;}
      std::istringstream is(line.substr(b+1)); double lon=0,lat=0; is>>lon>>lat;
      CGWCRS K; if (!K.Parse(line.substr(0,b),err)){fprintf(g,"0 0 0 0 0\n"); continue;}
      double x,y,lo,la; K.Forward(lon,lat,x,y); K.Inverse(x,y,lo,la); fprintf(g,"1 %.6f %.6f %.12f %.12f\n",x,y,lo,la);
    }
    fclose(g); }
  printf("done\n"); return 0;
}
