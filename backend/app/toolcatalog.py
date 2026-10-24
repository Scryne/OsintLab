"""Faz 32 — dış araç kataloğu (Launchpad).

Profesyonel OSINT pratiği tek bir araçla yapılmaz: analist bir seçiciyi bir düzine serviste açar.
Bu katalog o adımı tek tıka indirir — bir seçicinin sayfasında, o türü kabul eden her araç için
hazır bir bağlantı. **OsintLab bu araçlara istek ATMAZ**; bağlantı kullanıcının tarayıcısında açılır,
yani OPSEC kararı (giriş yapılmış hesap, VPN, tarayıcı profili) kullanıcınındır.

Kaynak: @osintnewsletter'ın OSINT Tools Library dizini (tools.osintnewsletter.com, 2026-10-24'te
335 araç) ve "Tool Tuesday" sayıları; buna altyapı/tehdit istihbaratı pratiğinin standart araçları
eklendi. Yalnızca ad, adres ve bağlantı kalıbı alındı; açıklamalar bu projenin kendi cümleleri.

Kalıcı kapsam sınırı burada da geçerli: kişi arama, kullanıcı adı taraması, telefon/e-posta ile
kişi bulma, yüz tanıma araçları katalogda YOK (hedef bazlı gözetim, Q25).

Bağlantı kalıbındaki yer tutucular: `{v}` ham değer, `{q}` URL-kodlanmış değer, `{domain}` (URL ya
da e-postadan türetilen alan adı), `{lat}` / `{lon}` (koordinat).
"""
from __future__ import annotations

from urllib.parse import quote, urlparse

CATEGORIES = {
    "infra": "Alan adı ve DNS",
    "network": "IP ve ağ",
    "threat": "Tehdit istihbaratı",
    "vuln": "Zafiyet",
    "archive": "Arşiv",
    "media": "Görsel ve video doğrulama",
    "geo": "Harita ve coğrafi konum",
    "transport": "Ulaşım",
    "crypto": "Blokzincir",
    "corporate": "Kurum, yaptırım, kayıt",
    "news": "Haber, arama ve teyit",
    "leaks": "Sızıntı ve belge arşivleri",
}

# cost: free | freemium | paid ; account: hesap gerekir mi
TOOLS: list[dict] = [
    # --- Alan adı ve DNS
    {"id": "dnsdumpster", "name": "DNSDumpster", "category": "infra", "url": "https://dnsdumpster.com/", "cost": "free", "account": False,
     "templates": {}, "note": "Alan adının DNS haritası; arama formu üzerinden."},
    {"id": "securitytrails", "name": "SecurityTrails", "category": "infra", "url": "https://securitytrails.com/", "cost": "freemium", "account": True,
     "templates": {"domain": "https://securitytrails.com/domain/{domain}/dns", "ip": "https://securitytrails.com/list/ip/{v}"},
     "note": "Geçmiş DNS kayıtları — bir alan adının eskiden nereye çözüldüğü."},
    {"id": "viewdns", "name": "ViewDNS.info", "category": "infra", "url": "https://viewdns.info/", "cost": "free", "account": False,
     "templates": {"domain": "https://viewdns.info/reversewhois/?q={domain}", "ip": "https://viewdns.info/reverseip/?host={v}&t=1"},
     "note": "Ters WHOIS ve ters IP (aynı sunucudaki diğer siteler)."},
    {"id": "domain-dossier", "name": "Domain Dossier (CentralOps)", "category": "infra", "url": "https://centralops.net/co/DomainDossier.aspx", "cost": "free", "account": False,
     "templates": {"domain": "https://centralops.net/co/DomainDossier.aspx?addr={domain}&dom_whois=true&dom_dns=true&net_whois=true",
                   "ip": "https://centralops.net/co/DomainDossier.aspx?addr={v}&net_whois=true"}},
    {"id": "crtsh-web", "name": "crt.sh", "category": "infra", "url": "https://crt.sh/", "cost": "free", "account": False,
     "templates": {"domain": "https://crt.sh/?q={domain}"}, "note": "Sertifika şeffaflığı kayıtları."},
    {"id": "have-i-been-squatted", "name": "Have I Been Squatted", "category": "infra", "url": "https://haveibeensquatted.com/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://haveibeensquatted.com/lookup/{domain}"}, "note": "Bir alan adını taklit eden (typosquat) kayıtlar."},
    {"id": "host-io", "name": "host.io", "category": "infra", "url": "https://host.io/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://host.io/{domain}"}, "note": "Aynı IP/ad sunucusunu ve analytics kimliğini paylaşan alan adları."},
    {"id": "builtwith", "name": "BuiltWith", "category": "infra", "url": "https://builtwith.com/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://builtwith.com/{domain}"}, "note": "Teknoloji yığını ve ilişkili siteler (ortak analytics/reklam kimliği)."},
    {"id": "publicwww", "name": "PublicWWW", "category": "infra", "url": "https://publicwww.com/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://publicwww.com/websites/%22{domain}%22/"}, "note": "Kaynak kodunda bir dizeyi (analytics kimliği, alan adı) geçiren siteler."},
    {"id": "dnstwister", "name": "dnstwister", "category": "infra", "url": "https://dnstwister.report/", "cost": "free", "account": False,
     "templates": {}, "note": "Typosquat alan adı üretip kayıtlı olanları gösterir."},
    # --- IP ve ağ
    {"id": "shodan", "name": "Shodan", "category": "network", "url": "https://www.shodan.io/", "cost": "freemium", "account": True,
     "templates": {"ip": "https://www.shodan.io/host/{v}", "domain": "https://www.shodan.io/search?query=hostname%3A{domain}",
                   "cve": "https://www.shodan.io/search?query=vuln%3A{v}"}},
    {"id": "censys", "name": "Censys", "category": "network", "url": "https://search.censys.io/", "cost": "freemium", "account": True,
     "templates": {"ip": "https://search.censys.io/hosts/{v}", "domain": "https://search.censys.io/search?resource=hosts&q={domain}"}},
    {"id": "fofa", "name": "FOFA", "category": "network", "url": "https://en.fofa.info/", "cost": "freemium", "account": True,
     "templates": {}, "note": "Shodan benzeri internet tarama motoru (OSINT Newsletter #126, Tool Tuesday). Sorgu dili base64 parametre ister; arama kutusundan."},
    {"id": "netlas", "name": "Netlas", "category": "network", "url": "https://app.netlas.io/", "cost": "freemium", "account": True,
     "templates": {"ip": "https://app.netlas.io/host/{v}/", "domain": "https://app.netlas.io/domains/?q=domain%3A{domain}"}},
    {"id": "leakix", "name": "LeakIX", "category": "network", "url": "https://leakix.net/", "cost": "freemium", "account": False,
     "templates": {"ip": "https://leakix.net/host/{v}", "domain": "https://leakix.net/domain/{domain}"}, "note": "Açıkta kalan servisler ve sızıntılar."},
    {"id": "ipinfo", "name": "IPinfo", "category": "network", "url": "https://ipinfo.io/", "cost": "freemium", "account": False,
     "templates": {"ip": "https://ipinfo.io/{v}", "asn": "https://ipinfo.io/{v}"}},
    {"id": "bgp-he", "name": "Hurricane Electric BGP Toolkit", "category": "network", "url": "https://bgp.he.net/", "cost": "free", "account": False,
     "templates": {"ip": "https://bgp.he.net/ip/{v}", "asn": "https://bgp.he.net/{v}", "domain": "https://bgp.he.net/dns/{domain}"}},
    {"id": "bgpview", "name": "RIPEstat", "category": "network", "url": "https://stat.ripe.net/", "cost": "free", "account": False,
     "templates": {"ip": "https://stat.ripe.net/{v}", "asn": "https://stat.ripe.net/{v}"}},
    {"id": "arin", "name": "ARIN Whois", "category": "network", "url": "https://search.arin.net/", "cost": "free", "account": False,
     "templates": {"ip": "https://search.arin.net/rdap/?query={v}", "asn": "https://search.arin.net/rdap/?query={v}"}},
    {"id": "greynoise", "name": "GreyNoise", "category": "network", "url": "https://viz.greynoise.io/", "cost": "freemium", "account": False,
     "templates": {"ip": "https://viz.greynoise.io/ip/{v}"}, "note": "Bir IP internet çapında tarama yapan bilinen bir 'gürültü' kaynağı mı?"},
    # --- Tehdit istihbaratı
    {"id": "virustotal", "name": "VirusTotal", "category": "threat", "url": "https://www.virustotal.com/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://www.virustotal.com/gui/domain/{domain}", "ip": "https://www.virustotal.com/gui/ip-address/{v}",
                   "url": "https://www.virustotal.com/gui/search/{q}", "md5": "https://www.virustotal.com/gui/file/{v}",
                   "sha1": "https://www.virustotal.com/gui/file/{v}", "sha256": "https://www.virustotal.com/gui/file/{v}"},
     "note": "Arama herkese açık değil ama yüklenen dosyalar öyle — hassas bir dosyayı YÜKLEME, yalnızca hash ara."},
    {"id": "urlscan", "name": "urlscan.io", "category": "threat", "url": "https://urlscan.io/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://urlscan.io/search/#domain%3A{domain}", "ip": "https://urlscan.io/search/#ip%3A{v}",
                   "url": "https://urlscan.io/search/#page.url%3A%22{q}%22"},
     "note": "Yeni tarama göndermek herkese açık bir kayıt bırakır; yalnızca ara."},
    {"id": "otx", "name": "AlienVault OTX", "category": "threat", "url": "https://otx.alienvault.com/", "cost": "free", "account": False,
     "templates": {"domain": "https://otx.alienvault.com/indicator/domain/{domain}", "ip": "https://otx.alienvault.com/indicator/ip/{v}",
                   "md5": "https://otx.alienvault.com/indicator/file/{v}", "sha1": "https://otx.alienvault.com/indicator/file/{v}",
                   "sha256": "https://otx.alienvault.com/indicator/file/{v}", "cve": "https://otx.alienvault.com/indicator/cve/{v}"}},
    {"id": "threatfox", "name": "ThreatFox", "category": "threat", "url": "https://threatfox.abuse.ch/", "cost": "free", "account": False,
     "templates": {"domain": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{domain}", "ip": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{v}",
                   "md5": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{v}", "sha256": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{v}"}},
    {"id": "urlhaus", "name": "URLhaus", "category": "threat", "url": "https://urlhaus.abuse.ch/", "cost": "free", "account": False,
     "templates": {"domain": "https://urlhaus.abuse.ch/browse.php?search={domain}", "ip": "https://urlhaus.abuse.ch/browse.php?search={v}",
                   "url": "https://urlhaus.abuse.ch/browse.php?search={q}"}},
    {"id": "malwarebazaar", "name": "MalwareBazaar", "category": "threat", "url": "https://bazaar.abuse.ch/", "cost": "free", "account": False,
     "templates": {"md5": "https://bazaar.abuse.ch/browse.php?search=md5%3A{v}", "sha1": "https://bazaar.abuse.ch/browse.php?search=sha1%3A{v}",
                   "sha256": "https://bazaar.abuse.ch/sample/{v}/"}},
    {"id": "xforce", "name": "IBM X-Force Exchange", "category": "threat", "url": "https://exchange.xforce.ibmcloud.com/", "cost": "freemium", "account": False,
     "templates": {"ip": "https://exchange.xforce.ibmcloud.com/ip/{v}", "domain": "https://exchange.xforce.ibmcloud.com/url/{domain}",
                   "cve": "https://exchange.xforce.ibmcloud.com/search/{v}", "sha256": "https://exchange.xforce.ibmcloud.com/malware/{v}"}},
    {"id": "malpedia", "name": "Malpedia", "category": "threat", "url": "https://malpedia.caad.fkie.fraunhofer.de/", "cost": "free", "account": False,
     "templates": {}, "note": "Kötü amaçlı yazılım aileleri ve aktör ansiklopedisi."},
    {"id": "abuseipdb", "name": "AbuseIPDB", "category": "threat", "url": "https://www.abuseipdb.com/", "cost": "freemium", "account": False,
     "templates": {"ip": "https://www.abuseipdb.com/check/{v}"}},
    {"id": "lookyloo", "name": "Lookyloo (CIRCL)", "category": "threat", "url": "https://lookyloo.circl.lu/", "cost": "free", "account": False,
     "templates": {}, "note": "Bir sayfanın yükleme ağacını yönlendirmeleriyle çıkarır (tarama gönderir — aktif)."},
    {"id": "mitre-attack", "name": "MITRE ATT&CK", "category": "threat", "url": "https://attack.mitre.org/", "cost": "free", "account": False,
     "templates": {"attack": "https://attack.mitre.org/techniques/{attack_path}/"}},
    # --- Zafiyet
    {"id": "nvd", "name": "NVD", "category": "vuln", "url": "https://nvd.nist.gov/", "cost": "free", "account": False,
     "templates": {"cve": "https://nvd.nist.gov/vuln/detail/{v}"}},
    {"id": "cve-org", "name": "CVE.org", "category": "vuln", "url": "https://www.cve.org/", "cost": "free", "account": False,
     "templates": {"cve": "https://www.cve.org/CVERecord?id={v}"}},
    {"id": "cisa-kev", "name": "CISA KEV", "category": "vuln", "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "cost": "free", "account": False,
     "templates": {"cve": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={v}"}},
    {"id": "exploit-db", "name": "Exploit-DB", "category": "vuln", "url": "https://www.exploit-db.com/", "cost": "free", "account": False,
     "templates": {"cve": "https://www.exploit-db.com/search?cve={cve_num}"}},
    {"id": "github-advisories", "name": "GitHub Advisory Database", "category": "vuln", "url": "https://github.com/advisories", "cost": "free", "account": False,
     "templates": {"cve": "https://github.com/advisories?query={v}"}},
    {"id": "vulners", "name": "Vulners", "category": "vuln", "url": "https://vulners.com/", "cost": "freemium", "account": False,
     "templates": {"cve": "https://vulners.com/cve/{v}"}},
    # --- Arşiv
    {"id": "wayback", "name": "Wayback Machine", "category": "archive", "url": "https://web.archive.org/", "cost": "free", "account": False,
     "templates": {"domain": "https://web.archive.org/web/*/{domain}/*", "url": "https://web.archive.org/web/*/{v}"}},
    {"id": "archive-today", "name": "archive.today", "category": "archive", "url": "https://archive.ph/", "cost": "free", "account": False,
     "templates": {"domain": "https://archive.ph/{domain}", "url": "https://archive.ph/{v}"}},
    {"id": "cachedview", "name": "CachedView", "category": "archive", "url": "https://cachedview.nl/", "cost": "free", "account": False, "templates": {}},
    {"id": "follow-that-page", "name": "Follow That Page", "category": "archive", "url": "https://www.followthatpage.com/", "cost": "free", "account": True,
     "templates": {}, "note": "Bir sayfadaki değişiklikleri e-postayla bildirir."},
    {"id": "arctic-shift", "name": "Arctic Shift", "category": "archive", "url": "https://arctic-shift.photon-reddit.com/", "cost": "free", "account": False,
     "templates": {}, "note": "Reddit arşivi araması."},
    # --- Görsel ve video doğrulama
    {"id": "google-lens", "name": "Google Lens", "category": "media", "url": "https://lens.google.com/", "cost": "free", "account": False,
     "templates": {"image_url": "https://lens.google.com/uploadbyurl?url={q}"}},
    {"id": "yandex-images", "name": "Yandex Görsel", "category": "media", "url": "https://yandex.com/images/", "cost": "free", "account": False,
     "templates": {"image_url": "https://yandex.com/images/search?rpt=imageview&url={q}"}, "note": "Yer ve bina eşleştirmede güçlü."},
    {"id": "tineye", "name": "TinEye", "category": "media", "url": "https://tineye.com/", "cost": "free", "account": False,
     "templates": {"image_url": "https://tineye.com/search?url={q}"}, "note": "Bir görselin internette ilk ne zaman göründüğü."},
    {"id": "bing-visual", "name": "Bing Visual Search", "category": "media", "url": "https://www.bing.com/visualsearch", "cost": "free", "account": False,
     "templates": {}, "note": "URL kalıbı güvenilir değil (2026-10 ölçümü); dosya yükleyerek."},
    {"id": "forensically", "name": "Forensically", "category": "media", "url": "https://29a.ch/photo-forensics/", "cost": "free", "account": False,
     "templates": {}, "note": "ELA, klon tespiti, gürültü analizi — tarayıcıda, yükleme yapmadan."},
    {"id": "fotoforensics", "name": "FotoForensics", "category": "media", "url": "https://fotoforensics.com/", "cost": "free", "account": False,
     "templates": {"image_url": "https://fotoforensics.com/upload-url.php?url={q}"}},
    {"id": "invid", "name": "InVID / WeVerify eklentisi", "category": "media", "url": "https://www.invid-project.eu/tools-and-services/invid-verification-plugin/", "cost": "free", "account": False,
     "templates": {}, "note": "Video kare çıkarma, ters arama, metadata — gazetecilerin standart eklentisi."},
    {"id": "c2pa", "name": "Content Credentials (C2PA)", "category": "media", "url": "https://contentcredentials.org/verify", "cost": "free", "account": False,
     "templates": {}, "note": "Görselde içerik kimlik bilgisi (üretici/AI imzası) var mı."},
    {"id": "filmot", "name": "Filmot", "category": "media", "url": "https://filmot.com/", "cost": "free", "account": False,
     "templates": {}, "note": "YouTube altyazılarında arama — bir ifadenin hangi videoda geçtiği."},
    # --- Harita ve coğrafi konum
    {"id": "google-maps", "name": "Google Maps", "category": "geo", "url": "https://www.google.com/maps", "cost": "free", "account": False,
     "templates": {"coord": "https://www.google.com/maps/@{lat},{lon},18z"}},
    {"id": "google-earth", "name": "Google Earth", "category": "geo", "url": "https://earth.google.com/web/", "cost": "free", "account": False,
     "templates": {"coord": "https://earth.google.com/web/@{lat},{lon},300a,1000d,35y,0h,0t,0r"}},
    {"id": "osm", "name": "OpenStreetMap", "category": "geo", "url": "https://www.openstreetmap.org/", "cost": "free", "account": False,
     "templates": {"coord": "https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"}},
    {"id": "sentinel-hub", "name": "Copernicus Browser", "category": "geo", "url": "https://browser.dataspace.copernicus.eu/", "cost": "free", "account": False,
     "templates": {"coord": "https://browser.dataspace.copernicus.eu/?zoom=14&lat={lat}&lng={lon}"}, "note": "Sentinel uydu görüntüleri, tarihe göre."},
    {"id": "mapillary", "name": "Mapillary", "category": "geo", "url": "https://www.mapillary.com/app/", "cost": "free", "account": False,
     "templates": {"coord": "https://www.mapillary.com/app/?lat={lat}&lng={lon}&z=17"}, "note": "Kitle kaynaklı sokak görüntüsü."},
    {"id": "suncalc", "name": "SunCalc", "category": "geo", "url": "https://www.suncalc.org/", "cost": "free", "account": False,
     "templates": {"coord": "https://www.suncalc.org/#/{lat},{lon},17/null/null/null/null"}, "note": "Güneş yönü ve gölge (kronolokasyon)."},
    {"id": "peakvisor", "name": "PeakVisor", "category": "geo", "url": "https://peakvisor.com/", "cost": "freemium", "account": False,
     "templates": {}, "note": "Dağ silüetinden konum doğrulama."},
    {"id": "bellingcat-osm", "name": "Bellingcat OSM Search", "category": "geo", "url": "https://osm-search.bellingcat.com/", "cost": "free", "account": False,
     "templates": {}, "note": "'Kilise + 200 m içinde köprü' gibi nesne kombinasyonlarıyla yer arama."},
    {"id": "geohints", "name": "GeoHints", "category": "geo", "url": "https://geohints.com/", "cost": "free", "account": False,
     "templates": {}, "note": "Ülkeye göre direk, plaka, yol işareti ipuçları."},
    {"id": "wikimapia", "name": "Wikimapia", "category": "geo", "url": "https://wikimapia.org/", "cost": "free", "account": False,
     "templates": {"coord": "https://wikimapia.org/#lat={lat}&lon={lon}&z=17"}},
    {"id": "open-infra-map", "name": "Open Infrastructure Map", "category": "geo", "url": "https://openinframap.org/", "cost": "free", "account": False,
     "templates": {"coord": "https://openinframap.org/#14/{lat}/{lon}"}, "note": "Enerji hatları, boru hatları, telekom altyapısı."},
    {"id": "liveuamap", "name": "Liveuamap", "category": "geo", "url": "https://liveuamap.com/", "cost": "freemium", "account": False,
     "templates": {}, "note": "Çatışma ve olay haritası."},
    # --- Ulaşım
    {"id": "adsbexchange", "name": "ADS-B Exchange", "category": "transport", "url": "https://globe.adsbexchange.com/", "cost": "free", "account": False,
     "templates": {"coord": "https://globe.adsbexchange.com/?lat={lat}&lon={lon}&zoom=9"}, "note": "Filtrelenmemiş uçuş verisi (askeri dahil)."},
    {"id": "flightradar24", "name": "Flightradar24", "category": "transport", "url": "https://www.flightradar24.com/", "cost": "freemium", "account": False,
     "templates": {"coord": "https://www.flightradar24.com/{lat},{lon}/9"}},
    {"id": "marinetraffic", "name": "MarineTraffic", "category": "transport", "url": "https://www.marinetraffic.com/", "cost": "freemium", "account": False,
     "templates": {"coord": "https://www.marinetraffic.com/en/ais/home/centerx:{lon}/centery:{lat}/zoom:10"}},
    {"id": "global-fishing-watch", "name": "Global Fishing Watch", "category": "transport", "url": "https://globalfishingwatch.org/map/", "cost": "free", "account": False,
     "templates": {}, "note": "Balıkçı gemisi hareketleri ve AIS karartmaları."},
    {"id": "openrailwaymap", "name": "OpenRailwayMap", "category": "transport", "url": "https://www.openrailwaymap.org/", "cost": "free", "account": False,
     "templates": {"coord": "https://www.openrailwaymap.org/?lat={lat}&lon={lon}&zoom=14"}},
    {"id": "faa-registry", "name": "FAA Uçak Sicili", "category": "transport", "url": "https://registry.faa.gov/aircraftinquiry/", "cost": "free", "account": False,
     "templates": {}, "note": "N-numaralı uçağın sahibi (OSINT Newsletter #127)."},
    {"id": "liveatc", "name": "LiveATC", "category": "transport", "url": "https://www.liveatc.net/", "cost": "free", "account": False, "templates": {}},
    {"id": "import-yeti", "name": "ImportYeti", "category": "transport", "url": "https://www.importyeti.com/", "cost": "free", "account": False,
     "templates": {}, "note": "ABD gümrük konşimentoları — bir şirketin tedarikçileri."},
    # --- Blokzincir
    {"id": "blockchair", "name": "Blockchair", "category": "crypto", "url": "https://blockchair.com/", "cost": "freemium", "account": False,
     "templates": {"btc": "https://blockchair.com/bitcoin/address/{v}", "eth": "https://blockchair.com/ethereum/address/{v}"}},
    {"id": "mempool", "name": "mempool.space", "category": "crypto", "url": "https://mempool.space/", "cost": "free", "account": False,
     "templates": {"btc": "https://mempool.space/address/{v}"}},
    {"id": "etherscan", "name": "Etherscan", "category": "crypto", "url": "https://etherscan.io/", "cost": "free", "account": False,
     "templates": {"eth": "https://etherscan.io/address/{v}"}},
    {"id": "arkham", "name": "Arkham Intelligence", "category": "crypto", "url": "https://intel.arkm.com/", "cost": "freemium", "account": True,
     "templates": {"btc": "https://intel.arkm.com/explorer/address/{v}", "eth": "https://intel.arkm.com/explorer/address/{v}"},
     "note": "Adreslerin bilinen kuruluşlara (borsa, servis) etiketlenmesi."},
    {"id": "walletexplorer", "name": "WalletExplorer", "category": "crypto", "url": "https://www.walletexplorer.com/", "cost": "free", "account": False,
     "templates": {"btc": "https://www.walletexplorer.com/address/{v}"}, "note": "Bitcoin adres kümeleme."},
    {"id": "bitcoinwhoswho", "name": "Bitcoin Who's Who", "category": "crypto", "url": "https://www.bitcoinwhoswho.com/", "cost": "freemium", "account": False,
     "templates": {"btc": "https://www.bitcoinwhoswho.com/address/{v}"}, "note": "Adresin dolandırıcılık bildirimleri ve web'de geçtiği yerler."},
    {"id": "dune", "name": "Dune", "category": "crypto", "url": "https://dune.com/", "cost": "freemium", "account": True, "templates": {}},
    # --- Kurum, yaptırım, kayıt
    {"id": "opencorporates", "name": "OpenCorporates", "category": "corporate", "url": "https://opencorporates.com/", "cost": "freemium", "account": False,
     "templates": {"entity": "https://opencorporates.com/companies?q={q}"}},
    {"id": "gleif-search", "name": "GLEIF LEI Search", "category": "corporate", "url": "https://search.gleif.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://search.gleif.org/#/search/simpleSearch={q}"}},
    {"id": "opensanctions", "name": "OpenSanctions", "category": "corporate", "url": "https://www.opensanctions.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://www.opensanctions.org/search/?q={q}", "btc": "https://www.opensanctions.org/search/?q={v}",
                   "eth": "https://www.opensanctions.org/search/?q={v}"}},
    {"id": "ofac-search", "name": "OFAC Sanctions List Search", "category": "corporate", "url": "https://sanctionssearch.ofac.treas.gov/", "cost": "free", "account": False,
     "templates": {}},
    {"id": "eu-sanctions-map", "name": "EU Sanctions Map", "category": "corporate", "url": "https://www.sanctionsmap.eu/", "cost": "free", "account": False, "templates": {}},
    {"id": "offshore-leaks", "name": "ICIJ Offshore Leaks", "category": "corporate", "url": "https://offshoreleaks.icij.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://offshoreleaks.icij.org/search?q={q}"}},
    {"id": "companies-house", "name": "Companies House (UK)", "category": "corporate", "url": "https://find-and-update.company-information.service.gov.uk/", "cost": "free", "account": False,
     "templates": {"entity": "https://find-and-update.company-information.service.gov.uk/search/companies?q={q}"}},
    {"id": "north-data", "name": "North Data", "category": "corporate", "url": "https://www.northdata.com/", "cost": "freemium", "account": False,
     "templates": {"entity": "https://www.northdata.com/{q}"}, "note": "Avrupa şirket ilişki ağları."},
    {"id": "edgar", "name": "SEC EDGAR tam metin", "category": "corporate", "url": "https://efts.sec.gov/LATEST/search-index?q=", "cost": "free", "account": False,
     "templates": {"entity": "https://www.sec.gov/edgar/search/#/q=%22{q}%22"}},
    {"id": "littlesis", "name": "LittleSis", "category": "corporate", "url": "https://littlesis.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://littlesis.org/search?q={q}"}, "note": "Kurum ve yönetici ilişki ağı."},
    {"id": "wikidata-web", "name": "Wikidata", "category": "corporate", "url": "https://www.wikidata.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://www.wikidata.org/w/index.php?search={q}"}},
    {"id": "opensecrets", "name": "OpenSecrets", "category": "corporate", "url": "https://www.opensecrets.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://www.opensecrets.org/search?q={q}"}, "note": "ABD lobi ve siyasi bağış kayıtları."},
    # --- Haber, arama ve teyit
    {"id": "gdelt-web", "name": "GDELT", "category": "news", "url": "https://api.gdeltproject.org/api/v2/summary/summary", "cost": "free", "account": False,
     "templates": {"entity": "https://api.gdeltproject.org/api/v2/doc/doc?query=%22{q}%22&mode=artlist&timespan=3months",
                   "cve": "https://api.gdeltproject.org/api/v2/doc/doc?query=%22{v}%22&mode=artlist&timespan=3months"}},
    {"id": "google-news", "name": "Google News", "category": "news", "url": "https://news.google.com/", "cost": "free", "account": False,
     "templates": {"entity": "https://news.google.com/search?q=%22{q}%22", "cve": "https://news.google.com/search?q={v}",
                   "domain": "https://news.google.com/search?q=%22{domain}%22"}},
    {"id": "google-fact-check", "name": "Google Fact Check Explorer", "category": "news", "url": "https://toolbox.google.com/factcheck/explorer", "cost": "free", "account": False,
     "templates": {"entity": "https://toolbox.google.com/factcheck/explorer/search/{q}"}},
    {"id": "mbfc", "name": "Media Bias/Fact Check", "category": "news", "url": "https://mediabiasfactcheck.com/", "cost": "free", "account": False,
     "templates": {"domain": "https://mediabiasfactcheck.com/?s={domain}"}, "note": "Kaynak güvenilirliği değerlendirmesi — Source.reliability'ye girdi."},
    {"id": "telegago", "name": "Telegago", "category": "news", "url": "https://cse.google.com/cse?cx=006368593537057042503:efxu7xprihg", "cost": "free", "account": False,
     "templates": {"entity": "https://cse.google.com/cse?cx=006368593537057042503:efxu7xprihg#gsc.q={q}",
                   "domain": "https://cse.google.com/cse?cx=006368593537057042503:efxu7xprihg#gsc.q={domain}",
                   "cve": "https://cse.google.com/cse?cx=006368593537057042503:efxu7xprihg#gsc.q={v}"},
     "note": "Herkese açık Telegram kanallarında arama (OSINT Newsletter #123)."},
    {"id": "europe-media-monitor", "name": "Europe Media Monitor", "category": "news", "url": "https://emm.newsbrief.eu/", "cost": "free", "account": False, "templates": {}},
    {"id": "searx", "name": "DuckDuckGo", "category": "news", "url": "https://duckduckgo.com/", "cost": "free", "account": False,
     "templates": {"entity": "https://duckduckgo.com/?q=%22{q}%22", "domain": "https://duckduckgo.com/?q=%22{domain}%22",
                   "md5": "https://duckduckgo.com/?q=%22{v}%22", "sha256": "https://duckduckgo.com/?q=%22{v}%22",
                   "btc": "https://duckduckgo.com/?q=%22{v}%22", "eth": "https://duckduckgo.com/?q=%22{v}%22"}},
    # --- Sızıntı ve belge arşivleri
    {"id": "library-of-leaks", "name": "Library of Leaks (DDoSecrets)", "category": "leaks", "url": "https://search.libraryofleaks.org/", "cost": "free", "account": False,
     "templates": {"entity": "https://search.libraryofleaks.org/search?q={q}", "domain": "https://search.libraryofleaks.org/search?q={domain}"},
     "note": "Sızdırılmış belge koleksiyonlarında tam metin arama (OSINT Newsletter #118)."},
    {"id": "aleph", "name": "OCCRP Aleph", "category": "leaks", "url": "https://aleph.occrp.org/", "cost": "free", "account": True,
     "templates": {"entity": "https://aleph.occrp.org/search?q={q}"}},
    {"id": "grayhatwarfare", "name": "GrayHatWarfare", "category": "leaks", "url": "https://buckets.grayhatwarfare.com/", "cost": "freemium", "account": False,
     "templates": {"domain": "https://buckets.grayhatwarfare.com/files?keywords={domain}"}, "note": "Açık bırakılmış bulut depolama kovaları."},
    {"id": "eyedex", "name": "EyeDex", "category": "leaks", "url": "https://www.eyedex.org/", "cost": "free", "account": False,
     "templates": {}, "note": "Açık dizin (open directory) arama motoru (OSINT Newsletter #112)."},
    {"id": "annas-archive", "name": "Anna's Archive", "category": "leaks", "url": "https://annas-archive.org/", "cost": "free", "account": False,
     "templates": {}, "note": "Kitap ve makale arşivi."},
]


def _domain_from(kind: str, value: str) -> str:
    if kind == "domain":
        return value
    if kind == "email":
        return value.rsplit("@", 1)[-1]
    if kind == "url":
        return urlparse(value).hostname or value
    return value


def render(template: str, kind: str, value: str) -> str:
    lat = lon = ""
    if kind == "coord":
        lat, _, lon = value.partition(",")
    attack_path = value.replace(".", "/") if kind == "attack" else ""
    cve_num = value.split("-", 1)[1] if kind == "cve" and "-" in value else ""
    return template.format(
        v=value, q=quote(value, safe=""), domain=_domain_from(kind, value), lat=lat, lon=lon,
        attack_path=attack_path, cve_num=cve_num,
    )


def links_for(kind: str, value: str) -> list[dict]:
    """Bir seçici (ya da `kind="entity"` ile bir kurum adı) için hazır bağlantılar. URL ve e-posta,
    kendi kalıbı olmayan araçlarda alan adı kalıbına düşer."""
    out = []
    for tool in TOOLS:
        templates = tool["templates"]
        if kind in templates:
            url = render(templates[kind], kind, value)
        elif kind in ("url", "email") and "domain" in templates:
            url = render(templates["domain"], "domain", _domain_from(kind, value))
        else:
            continue
        out.append({
            "tool_id": tool["id"],
            "name": tool["name"],
            "category": tool["category"],
            "category_label": CATEGORIES[tool["category"]],
            "url": url,
            "cost": tool["cost"],
            "account": tool["account"],
            "note": tool.get("note"),
        })
    return out


# --- Arama operatörü (dork) tarifleri ---------------------------------------------------
#
# Bir değeri arama motorlarında "doğru soruyla" aramak, çoğu zaman en verimli pasif adımdır:
# bir alan adının belgelerini, bir hash'in yapıştırma sitelerinde geçtiği yerleri, bir CVE'nin
# kod depolarındaki istismar örneklerini bulur. Tarifler türe göre sabit ve deterministik.
ENGINES = {
    "google": ("Google", "https://www.google.com/search?q={q}"),
    "bing": ("Bing", "https://www.bing.com/search?q={q}"),
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/?q={q}"),
    "yandex": ("Yandex", "https://yandex.com/search/?text={q}"),
}

_PASTE_SITES = "(site:pastebin.com OR site:paste.ee OR site:ghostbin.site OR site:rentry.co OR site:justpaste.it)"
_CODE_SITES = "(site:github.com OR site:gitlab.com OR site:bitbucket.org)"
_DOC_TYPES = "(filetype:pdf OR filetype:doc OR filetype:docx OR filetype:xls OR filetype:xlsx OR filetype:ppt OR filetype:pptx)"

DORK_RECIPES: dict[str, list[tuple[str, str]]] = {
    "domain": [
        ("Sitede belgeler", 'site:{domain} ' + _DOC_TYPES),
        ("Alt alan adları (www hariç)", "site:*.{domain} -site:www.{domain}"),
        ("Giriş/yönetim sayfaları", "site:{domain} (inurl:login OR inurl:admin OR inurl:portal OR intitle:login)"),
        ("Açık dizinler", 'site:{domain} intitle:"index of"'),
        ("Yapılandırma/yedek dosyaları", "site:{domain} (ext:env OR ext:bak OR ext:sql OR ext:log OR ext:conf OR ext:ini)"),
        ("Kendisi dışında adının geçtiği yerler", '"{domain}" -site:{domain}'),
        ("Yapıştırma sitelerinde", '"{domain}" ' + _PASTE_SITES),
        ("Kod depolarında", '"{domain}" ' + _CODE_SITES),
    ],
    "ip": [
        ("Adresin geçtiği yerler", '"{v}"'),
        ("Yapıştırma sitelerinde", '"{v}" ' + _PASTE_SITES),
        ("Tehdit raporlarında", '"{v}" (malware OR c2 OR "command and control" OR phishing OR botnet)'),
    ],
    "cve": [
        ("İstismar kodu", '"{v}" (exploit OR poc OR "proof of concept") ' + _CODE_SITES),
        ("Teknik analizler", '"{v}" (analysis OR writeup OR "root cause")'),
        ("Aktif sömürü haberleri", '"{v}" ("exploited in the wild" OR "actively exploited" OR ransomware)'),
        ("Resmi tavsiyeler", '"{v}" (site:cisa.gov OR site:cert.europa.eu OR site:ncsc.gov.uk OR site:usom.gov.tr)'),
    ],
    "md5": [("Hash'in geçtiği yerler", '"{v}"'), ("Kötü amaçlı yazılım analizleri", '"{v}" (malware OR sandbox OR analysis)')],
    "sha1": [("Hash'in geçtiği yerler", '"{v}"'), ("Kötü amaçlı yazılım analizleri", '"{v}" (malware OR sandbox OR analysis)')],
    "sha256": [("Hash'in geçtiği yerler", '"{v}"'), ("Kötü amaçlı yazılım analizleri", '"{v}" (malware OR sandbox OR analysis)')],
    "url": [("Adresin geçtiği yerler", '"{v}"'), ("Alan adının belgeleri", "site:{domain} " + _DOC_TYPES)],
    "email": [("Kurum alan adının belgeleri", "site:{domain} " + _DOC_TYPES), ("Adresin geçtiği yerler", '"{v}"')],
    "attack": [("Tekniğin geçtiği raporlar", '"{v}" (report OR "threat actor" OR campaign)')],
    "btc": [("Adresin geçtiği yerler", '"{v}"'), ("Dolandırıcılık bildirimleri", '"{v}" (scam OR ransom OR fraud OR sanction)')],
    "eth": [("Adresin geçtiği yerler", '"{v}"'), ("Dolandırıcılık bildirimleri", '"{v}" (scam OR ransom OR fraud OR sanction OR drainer)')],
    "asn": [("ASN'nin geçtiği yerler", '"{v}" (abuse OR "bulletproof" OR hosting)')],
    "entity": [
        ("Kurumun belgeleri", '"{v}" ' + _DOC_TYPES),
        ("Resmi kayıt ve ihaleler", '"{v}" (tender OR contract OR registry OR "annual report")'),
        ("Yaptırım ve soruşturma haberleri", '"{v}" (sanction OR indictment OR investigation OR lawsuit)'),
        ("Sızıntı ve yapıştırma sitelerinde", '"{v}" ' + _PASTE_SITES),
        ("Kod depolarında", '"{v}" ' + _CODE_SITES),
    ],
}


def dorks_for(kind: str, value: str) -> list[dict]:
    domain = _domain_from(kind, value)
    out = []
    for label, pattern in DORK_RECIPES.get(kind, []):
        query = pattern.format(v=value, domain=domain)
        out.append({
            "label": label,
            "query": query,
            "engines": [{"id": eid, "name": name, "url": url.format(q=quote(query, safe=""))} for eid, (name, url) in ENGINES.items()],
        })
    return out


def catalog() -> dict:
    return {
        "categories": [{"id": k, "label": v, "count": sum(1 for t in TOOLS if t["category"] == k)} for k, v in CATEGORIES.items()],
        "tools": [
            {**{k: v for k, v in t.items() if k != "templates"}, "category_label": CATEGORIES[t["category"]],
             "kinds": sorted(t["templates"].keys())}
            for t in TOOLS
        ],
    }
