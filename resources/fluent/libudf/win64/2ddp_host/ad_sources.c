#include "udf.h"
#include <stdio.h>
#include <stdlib.h>

/* -----------------------------------------------------------------
   Single actuator disk zone (cell zone ID = 7)

   Unlike the previous 27-zone model, all BEM annuli now live inside
   ONE Fluent cell zone. The radial load distribution is recovered by
   interpolating the per-station source terms at each cell centroid.

   Solver: 2D AXISYMMETRIC WITH SWIRL
     - xc[0] = axial coordinate  (x, along turbine axis)
     - xc[1] = radial coordinate (r >= 0)
     - momentum equations: axial-velocity, radial-velocity, swirl-velocity
     - source hooks: axial-velocity source  <- Sx_st
                     swirl-velocity source  <- Sw_st
   ----------------------------------------------------------------- */
#define AD_ZONE_ID 10

/* -----------------------------------------------------------------
   Source term storage (dynamically allocated, arbitrary station count)
   r[]  - radial coordinate of each BEM station              [m]
   Sx[] - axial momentum source at each station              [N/m^3]
   Sw[] - swirl (tangential) momentum source at station      [N/m^3]
   ----------------------------------------------------------------- */
static int   N_STATIONS = 0;
static real *r_st = NULL;
static real *Sx_st = NULL;
static real *Sw_st = NULL;
static int   sources_loaded = 0;

/* -----------------------------------------------------------------
   Free previously allocated station arrays
   ----------------------------------------------------------------- */
static void free_sources(void)
{
    if (r_st  != NULL) { free(r_st);  r_st  = NULL; }
    if (Sx_st != NULL) { free(Sx_st); Sx_st = NULL; }
    if (Sw_st != NULL) { free(Sw_st); Sw_st = NULL; }
    N_STATIONS     = 0;
    sources_loaded = 0;
}

/* -----------------------------------------------------------------
   Read actuator disk source terms from external file
   File format: "ad_sources.dat"
       line 1   : '#' header (skipped)
       line 2   : N                      (number of BEM stations)
       lines 3+ : r  Sx  Sw              (one line per station)
                  Sx = axial source, Sw = swirl source   [N/m^3]
   ----------------------------------------------------------------- */
DEFINE_ON_DEMAND(read_ad_sources)
{
    FILE *fp;
    int i;
    real r, sx, sw;

    Message("\n========================================\n");
    Message("   Reading actuator disk source terms\n");
    Message("   (single zone, radial interpolation)\n");
    Message("========================================\n");

    fp = fopen("ad_sources.dat", "r");
    if (!fp)
    {
        Message("\n[ERROR] Cannot open ad_sources.dat\n");
        Message("        File not found or inaccessible.\n\n");
        return;
    }

    /* Skip header line (assumes first line is column labels) */
    fscanf(fp, "%*[^\n]\n");

    /* Read number of stations */
    if (fscanf(fp, "%d", &i) != 1 || i <= 0)
    {
        Message("\n[ERROR] Could not read station count (N) from file.\n");
        fclose(fp);
        return;
    }

    /* (Re)allocate storage for arbitrary station counts */
    free_sources();
    N_STATIONS = i;
    r_st  = (real *)malloc(N_STATIONS * sizeof(real));
    Sx_st = (real *)malloc(N_STATIONS * sizeof(real));
    Sw_st = (real *)malloc(N_STATIONS * sizeof(real));

    if (r_st == NULL || Sx_st == NULL || Sw_st == NULL)
    {
        Message("\n[ERROR] Memory allocation failed for %d stations.\n", N_STATIONS);
        free_sources();
        fclose(fp);
        return;
    }

    Message("   Reading %d BEM stations...\n", N_STATIONS);

    for (i = 0; i < N_STATIONS; i++)
    {
        if (fscanf(fp, "%lf %lf %lf", &r, &sx, &sw) != 3)
        {
            Message("\n[ERROR] Malformed data at station %d\n", i+1);
            Message("        Expected: r  Sx  Sw\n");
            free_sources();
            fclose(fp);
            return;
        }

        r_st[i]  = r;
        Sx_st[i] = sx;
        Sw_st[i] = sw;

        /* Optional: display first few entries for verification */
        if (i < 5 || i == N_STATIONS-1) {
            Message("   r = %9.5f: Sx = %12.6f, Sw = %12.6f\n", r, sx, sw);
        } else if (i == 5) {
            Message("   ...\n");
        }
    }

    fclose(fp);

    /* Sanity check: stations must be sorted in increasing radius */
    for (i = 1; i < N_STATIONS; i++)
    {
        if (r_st[i] <= r_st[i-1])
        {
            Message("\n[ERROR] Station radii must be strictly increasing!\n");
            Message("        r(%d) = %g, r(%d) = %g\n\n", i, r_st[i-1], i+1, r_st[i]);
            free_sources();
            return;
        }
    }

    sources_loaded = 1;

    Message("\n[SUCCESS] Source terms loaded for %d stations on zone %d\n",
            N_STATIONS, AD_ZONE_ID);
    Message("========================================\n\n");
}

/* -----------------------------------------------------------------
   Linear interpolation of station data at radius r.
   Nearest-end clamping outside the station range.
   ----------------------------------------------------------------- */
static real interp_stations(real r, const real *values)
{
    int i;
    real frac;

    /* Below first station: clamp to first value */
    if (r <= r_st[0])
        return values[0];

    /* Above last station: clamp to last value */
    if (r >= r_st[N_STATIONS-1])
        return values[N_STATIONS-1];

    /* Locate surrounding stations (linear search is fine here) */
    for (i = 1; i < N_STATIONS; i++)
    {
        if (r <= r_st[i])
        {
            frac = (r - r_st[i-1]) / (r_st[i] - r_st[i-1]);
            return values[i-1] + frac * (values[i] - values[i-1]);
        }
    }

    return values[N_STATIONS-1];
}

/* -----------------------------------------------------------------
   Axial momentum source term (axissymmetric: hook to "axial-velocity")
   Applied to the single actuator disk zone; interpolated at the
   cell centroid radius.
   ----------------------------------------------------------------- */
DEFINE_SOURCE(ad_axial_source, c, t, dS, eqn)
{
    real xc[ND_ND];
    real r;

    /* Check if sources have been loaded */
    if (!sources_loaded)
    {
        Message("\n[WARNING] ad_axial_source called but no sources loaded!\n");
        Message("          Run 'read_ad_sources' on-demand first.\n\n");
        return 0.0;
    }

    /* Axisymmetric: xc[0] = axial, xc[1] = radial (already >= 0) */
    C_CENTROID(xc, c, t);
    r = xc[1];

    dS[eqn] = 0.0;  /* Derivative not used (explicit source) */
    return interp_stations(r, Sx_st);
}

/* -----------------------------------------------------------------
   Swirl momentum source term (axisymmetric-swirl: hook to
   "swirl-velocity"). Same radial interpolation as the axial source.
   NOTE: hooking this to the radial-velocity equation is WRONG for
   BEM - the tangential body force must go into the swirl equation.
   ----------------------------------------------------------------- */
DEFINE_SOURCE(ad_tangential_source, c, t, dS, eqn)
{
    real xc[ND_ND];
    real r;

    /* Check if sources have been loaded */
    if (!sources_loaded)
    {
        Message("\n[WARNING] ad_tangential_source called but no sources loaded!\n");
        Message("          Run 'read_ad_sources' on-demand first.\n\n");
        return 0.0;
    }

    /* Axisymmetric: xc[0] = axial, xc[1] = radial (already >= 0) */
    C_CENTROID(xc, c, t);
    r = xc[1];

    dS[eqn] = 0.0;  /* Derivative not used (explicit source) */
    return interp_stations(r, Sw_st);
}

/* -----------------------------------------------------------------
   Optional: Display current source terms for verification
   ----------------------------------------------------------------- */
DEFINE_ON_DEMAND(display_ad_sources)
{
    int i;

    Message("\n========================================\n");
    Message("   Current Actuator Disk Source Terms\n");
    Message("   Zone ID: %d\n", AD_ZONE_ID);
    Message("========================================\n");

    if (!sources_loaded)
    {
        Message("   [WARNING] No sources have been loaded yet.\n");
        Message("   Run 'read_ad_sources' first.\n");
        Message("========================================\n\n");
        return;
    }

    Message("   Station    r [m]      Sx (axial)    Sw (swirl)\n");
    Message("   -------    -------    ----------    ----------\n");

    for (i = 0; i < N_STATIONS; i++)
    {
        Message("   %4d       %9.5f    %12.6f    %12.6f\n",
                i+1, r_st[i], Sx_st[i], Sw_st[i]);
    }

    Message("========================================\n\n");
}
