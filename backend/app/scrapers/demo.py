"""Demo-mode scraper: generates realistic sample tenders so the whole product
(matching, scoring, alerts, reports, dashboards) can be evaluated locally
without a Firecrawl key or live portal access. Activated by DEMO_MODE=true."""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

from .base import BaseScraper, TenderRecord

TEMPLATES = [
    ("Supply of {n} Nos. Surveillance UAV / Drone Systems with Thermal Camera Payload",
     "Defence", "goods",
     "Procurement of unmanned aerial vehicle (UAV) systems with EO/IR thermal imaging "
     "payload for perimeter surveillance and ISR operations. Includes ground control "
     "station, spares and AMC for 3 years. RPAS certification under DGCA norms required."),
    ("Annual Rate Contract for Anti-Drone / Counter-UAS Detection Systems",
     "Defence", "goods",
     "Supply, installation and commissioning of counter-unmanned aerial system (C-UAS) "
     "with RF detection, radar and jamming capability for installation security."),
    ("Design, Development and Supply of Composite Materials for Aerospace Structures",
     "Aerospace", "goods",
     "Carbon fibre composite material panels and pre-preg supply for airframe assemblies, "
     "with NDT certification and traceability documentation."),
    ("Procurement of High Resolution PTZ CCTV Surveillance Cameras with VMS",
     "Security", "goods",
     "Supply and installation of IP based PTZ surveillance cameras, video management "
     "software, and 24x7 monitoring station equipment, including thermal camera units."),
    ("Hiring of Drone Survey Services for Revenue Village Mapping (SVAMITVA)",
     "Survey", "services",
     "Engagement of agency for drone-based large scale mapping of rural inhabited areas, "
     "RPAS pilots must hold DGCA remote pilot certificate. Deliverables: ortho-rectified imagery, GIS layers."),
    ("Construction of Approach Road and Boundary Wall at Industrial Estate",
     "PWD", "works",
     "Civil works including WBM road, CC drain, compound wall and gate at industrial estate. "
     "Contractor class A/B eligible. EMD as applicable."),
    ("Supply and Installation of Solar Rooftop Power Plant ({n} kWp) with Net Metering",
     "Energy", "goods",
     "Grid-connected rooftop solar photovoltaic system supply, installation, testing and "
     "commissioning with 5 year comprehensive maintenance contract."),
    ("Selection of Agency for GIS Based Asset Mapping using UAV Photogrammetry",
     "IT", "services",
     "Unmanned aerial vehicle based photogrammetry survey, LiDAR data acquisition and GIS "
     "database creation for urban local body assets."),
    ("Procurement of Laboratory Equipment for Materials Testing Facility",
     "R&D", "goods",
     "Universal testing machine, hardness testers and metallurgical microscopes for materials "
     "research laboratory, including installation and training."),
    ("Comprehensive AMC for IT Infrastructure, Servers and Networking Equipment",
     "IT", "services",
     "Annual maintenance contract covering servers, storage, firewalls, switches and end-user "
     "computing devices across district offices."),
    ("Supply of Bullet Proof Jackets and Ballistic Helmets - Level III+",
     "Defence", "goods",
     "Procurement of BIS certified ballistic protection equipment for state police special "
     "forces, including ballistic testing reports from accredited laboratory."),
    ("Empanelment of Vendors for Radar and Electronic Warfare Sub-systems",
     "Defence", "goods",
     "RFE for indigenous vendors for radar transmit-receive modules, antenna arrays and "
     "electronic warfare sub-systems under Make-in-India category."),
    ("Operation and Maintenance of Sewage Treatment Plant ({n} MLD)",
     "Urban", "services",
     "O&M contract for sewage treatment plant including manpower, consumables and adherence "
     "to PCB discharge norms for a period of 5 years."),
    ("Rate Contract for Supply of Office Furniture and Modular Workstations",
     "Admin", "goods",
     "Supply of ergonomic chairs, modular workstations and conference furniture to government "
     "offices on rate contract basis for one year."),
    ("Procurement of Ambulances with Advanced Life Support Equipment",
     "Health", "goods",
     "Type-D ambulances built on chassis with ALS medical equipment, patient monitoring "
     "systems and 5 year CMC."),
]

ORGS = [
    ("Directorate General of {state} Police", "Home Department"),
    ("Public Works Department, {state}", "Infrastructure Wing"),
    ("{state} Industrial Development Corporation", "Projects Division"),
    ("Defence Research & Development Organisation", "Aeronautics Cluster"),
    ("Indian Army - HQ Northern Command", "Procurement Cell"),
    ("Municipal Corporation", "Engineering Department"),
    ("Department of Science & Technology", "Survey Division"),
    ("Border Security Force", "Provisioning Directorate"),
    ("{state} Police Housing Corporation", "Technical Wing"),
    ("National Highways Authority of India", "Regional Office"),
]

STATES = ["Tamil Nadu", "Karnataka", "Andhra Pradesh", "Telangana", "Maharashtra",
          "Gujarat", "Uttar Pradesh", "Delhi", "Kerala", "Rajasthan"]


class DemoScraper(BaseScraper):
    """Generates deterministic-per-day sample tenders for any portal."""

    portal_code = "demo"

    def scrape(self, search_terms: list[str]) -> list[TenderRecord]:
        portal_code = getattr(self.portal, "code", "demo")
        portal_state = getattr(self.portal, "state", None)
        today = datetime.utcnow().date()
        # Deterministic per portal+day so repeated runs upsert the same refs
        seed = int(hashlib.sha256(f"{portal_code}:{today}".encode()).hexdigest(), 16)
        rng = random.Random(seed)

        records = []
        count = rng.randint(8, 14)
        for i in range(count):
            if i == 0:
                # One "hot" tender per portal/day: high-relevance combo that
                # exercises the >80 instant-alert path (title+desc+state+industry)
                tpl_title, dept_hint, category, description = TEMPLATES[0]
                org_tpl, dept = ORGS[3]  # DRDO
                state = portal_state or "Tamil Nadu"
            else:
                tpl_title, dept_hint, category, description = rng.choice(TEMPLATES)
                org_tpl, dept = rng.choice(ORGS)
                state = portal_state or rng.choice(STATES)
            title = tpl_title.format(n=rng.choice([2, 5, 10, 25, 50, 100]))
            if i == 0:
                published = today
                closing = datetime.utcnow() + timedelta(days=3, hours=4)
                serial = "HOT"
                value = 2.5e7
            else:
                published = today - timedelta(days=rng.randint(0, 6))
                closing = datetime.utcnow() + timedelta(days=rng.randint(2, 35),
                                                        hours=rng.randint(0, 23))
                serial = f"{i + 1:03d}"
                value = rng.choice([None, 4.8e5, 1.2e6, 7.5e6, 2.5e7, 9.9e7, 4.0e8])
            ref = f"{portal_code.upper()}/{published:%Y}/{seed % 9000 + 1000}/{serial}"
            records.append(TenderRecord(
                tender_ref_no=ref,
                title=title,
                organisation=org_tpl.format(state=state),
                department=f"{dept} ({dept_hint})",
                category=category,
                state=state,
                published_date=published,
                closing_date=closing,
                estimated_value=value,
                document_url=f"{self.base_url.rstrip('/')}/tender/{ref.replace('/', '-')}",
                raw_url=self.base_url,
                description_text=description,
                raw_html=f"<html><body><h1>{title}</h1><p>{description}</p></body></html>",
            ))
        self.logger.info("[DEMO MODE] generated %d sample tenders for %s",
                         len(records), portal_code)
        return records
