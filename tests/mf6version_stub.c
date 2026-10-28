/* Stand-in for the MODFLOW 6 library, for tests/mf6version_check.py: exports the functions Raven's CMF6Engine looks up;
   get_version reports the text of the environment variable STUB_MF6_VERSION (compiled with -DNO_GET_VERSION it has no
   get_version at all). initialize fails, so a run stops right after the version guard.
     cc -shared -fPIC -o libmf6_stub.so mf6version_stub.c [-DNO_GET_VERSION]                                         */
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
EXPORT int initialize(const char *c){(void)c; return 1;}
EXPORT int finalize(void){return 0;}
EXPORT int prepare_time_step(double *dt){(void)dt; return 1;}
EXPORT int finalize_time_step(void){return 1;}
EXPORT int prepare_solve(int *s){(void)s; return 1;}
EXPORT int solve(int *s,int *c){(void)s; (void)c; return 1;}
EXPORT int finalize_solve(int *s){(void)s; return 1;}
EXPORT int get_value_ptr(const char *n,void **p){(void)n; *p=NULL; return 1;}
EXPORT int get_var_address(const char *a,const char *b,const char *c,char *o){(void)a;(void)b;(void)c; o[0]='\0'; return 1;}
EXPORT int get_var_rank(const char *n,int *r){(void)n; *r=0; return 1;}
EXPORT int get_var_shape(const char *n,int *s){(void)n; s[0]=0; return 1;}
EXPORT int get_last_bmi_error(char *m){strcpy(m,"stand-in library of mf6version_check.py"); return 0;}
EXPORT int get_current_time(double *t){*t=0.0; return 0;}
#ifndef NO_GET_VERSION
EXPORT int get_version(char *v)
{
  const char *s=getenv("STUB_MF6_VERSION");
  if (s==NULL){s="6.8.1";}
  strncpy(v,s,511); v[511]='\0';
  return 0;
}
#endif
