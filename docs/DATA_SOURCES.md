# DATA SOURCES & INTEGRATION PATTERNS
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge Focus:** Planet X and SPHEREx

---

## 1. Integrated Scientific Data Sources

The **SPHEREx Visualizer & Object Identifier** aggregates data from five astronomical and geospatial services:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA SERVICE INVENTORY                          │
├────────────────────────────────┬───────────────────────────────────────┤
│ 1. Caltech/IPAC IRSA TAP       │ Live SPHEREx FITS Cutouts & Planes    │
│ 2. CDS Sesame (SIMBAD/NED)     │ Astronomical Name-to-Coordinate Resol.│
│ 3. ESA Gaia DR3                │ Optical Astrometry & Counterpart Match│
│ 4. NASA CatWISE 2020           │ Mid-Infrared Baseline (W1/W2 Photom.) │
│ 5. OpenStreetMap Nominatim     │ Geographic Geocoding & Overhead Zenith│
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 2. Integration Architectures & Protocols

### 2.1 Caltech/IPAC IRSA Table Access Protocol (TAP)
- **Endpoint:** `https://irsa.ipac.caltech.edu/TAP/sync`
- **Protocol:** IVOA Table Access Protocol (TAP) using Astronomical Data Query Language (ADQL).
- **Authentication:** Public Access (No API key required).
- **Schema & Query Template:**
  ```sql
  SELECT TOP 20 
    artifact.artifact_id, 
    artifact.uri, 
    artifact.time_bounds_lower, 
    artifact.time_bounds_upper,
    plane.wavelength_center, 
    plane.bandpass_name
  FROM spherex.artifact AS artifact
  JOIN spherex.plane AS plane ON artifact.artifact_id = plane.artifact_id
  WHERE 1=CONTAINS(POINT('ICRS', {ra_deg}, {dec_deg}), CIRCLE('ICRS', artifact.ra, artifact.dec, {size_deg}))
  ORDER BY artifact.time_bounds_lower ASC;
  ```
- **Post-Query Pipeline:**
  1. Frames are sorted chronologically by `time_bounds_lower` (MJD).
  2. Distinct survey epochs are extracted with the constraint $\Delta t \ge 150\,\text{days}$.
  3. FITS files are read, zodiacal background emission is subtracted via the `ZODI` HDU extension (`IMAGE - ZODI`), negative values are clipped, and an astronomical $\ln(1 + x)$ dynamic range stretch is applied.

---

### 2.2 CDS Sesame Astronomical Name Resolver
- **Provider:** Centre de Données astronomiques de Strasbourg (CDS).
- **Interface:** Automated query via `astropy.coordinates.SkyCoord.from_name(object_name)`.
- **Databases Queried:** SIMBAD, NED, VizieR.
- **Example Usage:**
  ```python
  from astropy.coordinates import SkyCoord
  coord = SkyCoord.from_name("Barnard's Star")
  ra_deg = float(coord.ra.deg)   # 269.452083
  dec_deg = float(coord.dec.deg) # 4.693389
  ```

---

### 2.3 ESA Gaia Data Release 3 (DR3) Cross-Matching
- **Role:** Optical verification filter for moving infrared candidates.
- **Criteria for Brown Dwarf / Planet X Candidates:**
  $$\text{Is Candidate} \iff (\mu > 1.0''/\text{yr}) \land (G_{\text{Gaia}} > 20.7 \lor \text{No Counterpart Within } 3.0'')$$
- **Science Logic:**
  Standard main-sequence stars (like Barnard's Star) possess bright Gaia optical counterparts ($G < 15\,\text{mag}$) that confirm cataloged status. Sub-stellar objects below $500\,\text{K}$ (such as WISE 0855) are completely invisible in Gaia optical bands ($G > 21.5$) but shine intensely across SPHEREx infrared channels $3 - 6$, triggering the **NEW CANDIDATE (UNCATALOGED)** mission-control alert.

---

### 2.4 NASA CatWISE 2020 Catalog
- **Role:** Mid-infrared color baseline ($W1 = 3.4\,\mu\text{m}$, $W2 = 4.6\,\mu\text{m}$).
- **Diagnostic Color:**
  $$W1 - W2 > 2.0\,\text{mag}$$
  A high $(W1 - W2)$ color index signals intense methane ($\nu_3$) absorption in $W1$ coupled with flux emergence in the $W2$ atmospheric window—a definitive fingerprint of cold brown dwarfs and outer planetary bodies.

---

### 2.5 OpenStreetMap Nominatim Overhead Zenith Conversion
- **Role:** Allows any user on Earth to view the SPHEREx infrared sky passing directly overhead above their city.
- **Endpoint:** `https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1`
- **Astronomical Coordinate Conversion:**
  1. Geocode location to Latitude ($\phi$) and Longitude ($\lambda$).
  2. Instantiate an `astropy.coordinates.EarthLocation(lat=phi*u.deg, lon=lambda*u.deg, height=0*u.m)`.
  3. Evaluate the Zenith vector in the local Horizontal frame:
     $$\text{Altitude} = 90.0^{\circ}, \quad \text{Azimuth} = 0.0^{\circ}$$
  4. Transform the `AltAz` coordinate to the International Celestial Reference System (`ICRS`) at current UTC time:
     ```python
     now = Time.now()
     zenith_altaz = AltAz(alt=90*u.deg, az=0*u.deg, obstime=now, location=loc)
     zenith_icrs = zenith_altaz.transform_to(ICRS())
     ```
  5. The resulting $(\alpha, \delta)$ coordinates are queried through SPHEREx.

