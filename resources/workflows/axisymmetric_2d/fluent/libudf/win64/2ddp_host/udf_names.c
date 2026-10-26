/* This file generated automatically. */
/*          Do not modify.            */
#include "udf.h"
#include "prop.h"
#include "dpm.h"
extern DEFINE_ON_DEMAND(read_ad_sources);
extern DEFINE_SOURCE(ad_axial_source, c, t, dS, eqn);
extern DEFINE_SOURCE(ad_tangential_source, c, t, dS, eqn);
extern DEFINE_ON_DEMAND(display_ad_sources);
__declspec(dllexport) UDF_Data udf_data[] = {
{"read_ad_sources", (void(*)())read_ad_sources, UDF_TYPE_ON_DEMAND},
{"ad_axial_source", (void(*)())ad_axial_source, UDF_TYPE_SOURCE},
{"ad_tangential_source", (void(*)())ad_tangential_source, UDF_TYPE_SOURCE},
{"display_ad_sources", (void(*)())display_ad_sources, UDF_TYPE_ON_DEMAND},
};
__declspec(dllexport) int n_udf_data = sizeof(udf_data)/sizeof(UDF_Data);
#include "version.h"
__declspec(dllexport) void UDF_Inquire_Release(int *major, int *minor, int *revision)
{
  *major = RampantReleaseMajor;
  *minor = RampantReleaseMinor;
  *revision = RampantReleaseRevision;
}
