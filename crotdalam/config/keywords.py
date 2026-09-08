"""Small auditable bilingual lexicons; heuristic signals, not ground truth.

Phrases are matched with word boundaries and each category scores once. The
Indonesian entries target fraud patterns common on TikTok Indonesia (robot
trading, titip dana, flip/gestun, pinjol ilegal, judol, "admin resmi"). These
are indicators for triage, never a determination — legitimate finance, gaming
and giveaway content will match, and quoted or educational content will too.
"""

SCAM_SIGNALS = {
    "guaranteed_returns": (30, (
        "guaranteed profit", "guaranteed returns", "double your money",
        "profit pasti", "pasti untung", "pasti profit", "tanpa risiko", "risk free",
        "auto profit", "cuan pasti", "keuntungan tetap", "profit harian", "bunga harian")),
    "investment_lure": (20, (
        "robot trading", "bot trading", "titip dana", "titip modal", "kelola dana",
        "trading signal", "sinyal trading", "binary option", "binary options",
        "forex signal", "crypto signal", "join vip", "grup vip", "member vip",
        "modal kecil untung besar", "balik modal")),
    "advance_fee": (25, (
        "pay upfront", "activation fee", "biaya admin", "biaya aktivasi",
        "transfer dulu", "deposit first", "biaya pencairan", "biaya pajak",
        "bayar pajak dulu", "top up dulu", "isi saldo dulu", "gestun", "flip saldo")),
    "credential_request": (35, (
        "send your otp", "share your password", "kirim otp", "kirim password",
        "kode verifikasi", "kode otp", "bagikan otp", "minta kode", "kode akun",
        "pin atm", "data rekening", "nomor kartu")),
    "loan_lure": (15, (
        "pinjol", "pinjaman online", "pinjaman cepat", "pinjaman tanpa jaminan",
        "cair tanpa bi checking", "dana cepat cair", "pinjaman langsung cair",
        "tanpa slip gaji", "limit besar")),
    "gambling": (15, (
        "slot gacor", "situs slot", "judi online", "judol", "maxwin", "scatter hitam",
        "akun pro", "rtp tinggi", "link slot", "deposit pulsa")),
    "urgency": (10, (
        "act now", "limited time", "last chance", "segera transfer", "hari ini saja",
        "buruan", "slot terbatas", "kuota terbatas", "jangan sampai kehabisan",
        "sebelum tutup", "promo berakhir")),
    "prize_bait": (15, (
        "you have won", "claim your prize", "anda menang", "klaim hadiah",
        "selamat anda terpilih", "pemenang undian", "hadiah langsung",
        "saldo gratis", "dana gratis", "top up gratis")),
    "impersonation": (20, (
        "admin resmi", "cs resmi", "akun resmi", "official account", "admin official",
        "layanan pelanggan resmi", "verified admin", "akun terverifikasi resmi")),
    "off_platform": (5, (
        "hubungi whatsapp", "chat telegram", "contact whatsapp", "dm for details",
        "chat wa", "klik link di bio", "cek bio", "link di komentar",
        "gabung telegram", "join telegram", "invite whatsapp")),
}

# Single tokens only: TOKEN_PATTERN cannot match phrases. "terima kasih"
# was previously split into "terima"/"kasih", which alone mean accept/give.
POSITIVE_WORDS = frozenset((
    "good great excellent love happy thanks amazing safe helpful trusted legit reliable "
    "bagus baik mantap suka senang makasih aman membantu keren terpercaya jujur puas amanah recommended"
).split())
NEGATIVE_WORDS = frozenset((
    "bad awful hate sad scam fraud terrible unsafe fake warning avoid "
    "buruk jelek benci sedih penipuan tipu penipu berbahaya kecewa bohong hoax waspada hindari abal"
).split())
NEGATIONS = frozenset("not no never tidak tak bukan jangan gak nggak ga engga enggak".split())
