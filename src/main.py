import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from pandas import DataFrame, concat
from jobspy import scrape_jobs

# Try importing google search for non-LinkedIn web mode
try:
    from googlesearch import search as google_search
    HAS_GOOGLE_SEARCH = True
except ImportError:
    HAS_GOOGLE_SEARCH = False

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
APPS_DIR = BASE_DIR / "applications"

SEARCH_TERMS = [
    "Embedded C++ Intern",
    "Embedded Software Engineer Fresher",
    "Junior Embedded Engineer"
]
LOCATION = "India"

# Google Dorks targeting direct company career portals
RECENT_DATE = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
DORK_QUERIES = [
    f'site:greenhouse.io OR site:lever.co "Embedded" "India" ("Fresher" OR "Intern") after:{RECENT_DATE}',
    f'intitle:"Careers" "Embedded Engineer" "India" ("Junior" OR "Intern" OR "Fresher") after:{RECENT_DATE} -linkedin.com'
]

def get_job_keywords() -> str:
    return "C++17, FreeRTOS, STM32, Pointers, UART, SPI, I2C, Memory Management, Bare-Metal"

def extract_company_from_url(url: str) -> str:
    domain = re.sub(r'https?://(www\.)?', '', url).split('/')[0]
    name = domain.split('.')[0]
    return "".join(c for c in name if c.isalnum()).capitalize() or "WebCompany"

def run_pipeline():
    print(f"[*] Starting Dual Pipeline (LinkedIn + Web Direct Careers)...")
    
    all_jobs = []

    # -------------------------------------------------------------
    # 1. LINKEDIN SCRAPING
    # -------------------------------------------------------------
    for term in SEARCH_TERMS:
        try:
            print(f"[*] [LinkedIn] Fetching '{term}'...")
            jobs: DataFrame = scrape_jobs(
                site_name=["linkedin"],
                search_term=term,
                location=LOCATION,
                results_wanted=10,
                is_remote=False
            )
            if not jobs.empty:
                for _, row in jobs.iterrows():
                    all_jobs.append({
                        "company": str(row.get("company", "LinkedInCompany")),
                        "title": str(row.get("title", "Embedded Role")),
                        "job_url": str(row.get("job_url", "")),
                        "source": "LinkedIn"
                    })
        except Exception as e:
            print(f"[!] Warning on LinkedIn '{term}': {e}")

    # -------------------------------------------------------------
    # 2. WEB CAREER PORTALS SCRAPING
    # -------------------------------------------------------------
    if HAS_GOOGLE_SEARCH:
        print("[*] [Web Direct] Searching fresh company career portals...")
        for query in DORK_QUERIES:
            try:
                results = list(google_search(query, num_results=3, lang="en"))
                for url in results:
                    company = extract_company_from_url(url)
                    all_jobs.append({
                        "company": company,
                        "title": "Embedded Engineer (Fresher/Intern)",
                        "job_url": url,
                        "source": "Web Direct"
                    })
            except Exception as e:
                print(f"[!] Web search warning: {e}")

    if not all_jobs:
        print("[!] No listings discovered.")
        return

    # Deduplicate by URL
    df = DataFrame(all_jobs).drop_duplicates(subset=["job_url"])
    
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(APPS_DIR / "jobs_database.csv", index=False)
    
    total_found = len(df)
    print(f"\n[+] Total unique roles aggregated: {total_found}")

    # Compile LaTeX Resumes
    with open(SRC_DIR / "master_resume.tex", "r") as f:
        latex_code = f.read()

    keywords = get_job_keywords()
    tailored_latex = latex_code.replace(
        "Modern OOP, STL, RAII, Smart Pointers",
        f"Modern OOP, STL, RAII, Smart Pointers, {keywords}"
    )

    success_count = 0
    today_str = datetime.now().strftime('%Y-%m-%d')

    for idx, job in df.iterrows():
        raw_company = str(job["company"])
        company = "".join(c for c in raw_company if c.isalnum()) or f"Company_{idx+1}"
        role = str(job["title"])
        source = str(job["source"])
        
        target_app_dir = APPS_DIR / f"{today_str}_{company}"
        target_app_dir.mkdir(parents=True, exist_ok=True)

        tex_file = target_app_dir / "tailored.tex"

        with open(tex_file, "w") as f:
            f.write(tailored_latex)

        try:
            subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    f"-output-directory={target_app_dir}",
                    f"-jobname=resume",
                    str(tex_file)
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            success_count += 1
            print(f"[{success_count}/{total_found}] Built Resume [{source}] -> {company} ({role})")
        except Exception as e:
            print(f"[!] Compilation skipped for {company}: {e}")

    print("\n" + "="*60)
    print(f"SUCCESS: Pipeline complete! {success_count}/{total_found} resumes ready in applications/")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_pipeline()