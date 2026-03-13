# Beacon GoM — Logo & Branding Integration

## Logo Assets Available

The following brand assets have been created and are available in the project root under `assets/brand/`:

| File | Purpose | Where to Use |
|------|---------|-------------|
| `favicon.ico` | Browser tab icon (multi-size: 16, 32, 48) | `frontend/public/favicon.ico` |
| `favicon.svg` | Modern browsers favicon | `frontend/public/favicon.svg` |
| `favicon_16.png` | Smallest favicon | Fallback |
| `favicon_32.png` | Standard favicon | `<link rel="icon">` |
| `favicon_180.png` | Apple touch icon | `<link rel="apple-touch-icon">` |
| `favicon_192.png` | Android/PWA icon | `<link rel="icon" sizes="192x192">` |
| `beacon_gom_icon.svg` | Standalone beacon mark (circle) | App sidebar, loading screens |
| `beacon_icon_512.png` | Large icon PNG | OG meta image, PWA manifest |
| `beacon_icon_256.png` | Medium icon | General use |
| `beacon_icon_128.png` | Small icon | Inline references |
| `beacon_gom_logo_light.svg` | Full logo (icon + text) for light backgrounds | PDF report headers, print |
| `beacon_gom_logo_light.png` | Full logo PNG (1600x400) for light bg | PDF reports, email signatures |
| `beacon_gom_logo_dark.svg` | Full logo for dark backgrounds | App header/sidebar |
| `beacon_gom_logo_dark.png` | Full logo PNG (1600x400) for dark bg | App header |

## Integration Tasks

### 1. Browser Tab (Favicon)
Copy favicon files to `frontend/public/` and update `frontend/index.html`:

```html
<head>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon_32.png" />
  <link rel="icon" type="image/png" sizes="192x192" href="/favicon_192.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="/favicon_180.png" />
  <title>Beacon GoM — AI Safety Intelligence</title>
</head>
```

### 2. App Sidebar / Header
Add the logo to the app sidebar or top header. Use `beacon_gom_logo_dark.svg` on the dark sidebar, or `beacon_gom_icon.svg` if space is limited. The icon mark should link to the dashboard (home).

### 3. PDF Report Header
In `backend/services/report_service.py`, add the `beacon_gom_logo_light.png` as a header image on every generated PDF report. Place it top-left with the tagline "AI Safety & Regulatory Intelligence" to the right. This brands every report that gets shared externally.

### 4. Login / Landing Page (if applicable)
Use `beacon_icon_512.png` as a hero element centered above the app title.

### 5. OG Meta Tags (Social Sharing)
In `frontend/index.html`, add Open Graph meta tags so the logo appears when sharing links:

```html
<meta property="og:title" content="Beacon GoM — AI Safety Intelligence" />
<meta property="og:description" content="AI-powered safety analytics for Gulf of Mexico offshore operations" />
<meta property="og:image" content="/beacon_icon_512.png" />
<meta property="og:type" content="website" />
```

## Brand Colors (for reference)

| Name | Hex | Usage |
|------|-----|-------|
| Navy | `#0A1628` | Primary dark background, text on light bg |
| Deep Blue | `#0D2847` | Card backgrounds on dark |
| Teal | `#0891B2` | Primary accent, links, buttons |
| Teal Light | `#22D3EE` | Highlights, hover states, secondary accent |
| White | `#FFFFFF` | Text on dark, backgrounds |
| Off White | `#F0F9FF` | Light page backgrounds |
| Slate Gray | `#64748B` | Secondary text, captions |
| Dark Text | `#1E293B` | Primary text on light backgrounds |

## Implementation Notes
- The SVG versions are preferred for the web app (scalable, crisp at any size)
- The PNG versions are for contexts that don't support SVG (PDF generation, email, OG tags)
- The favicon.ico contains multiple sizes and works across all browsers including legacy IE
- All assets use the same navy + teal color palette as the rest of the app
