import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# --- SABİTLER ---
FAIZ_ORANI = 42.0
STOPAJ = 17.5
DARK_BG = "#0d1117"

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Akıncı Finans V10.5", layout="wide", initial_sidebar_state="expanded")

# --- VERİTABANI İŞLEMLERİ ---
def db_kur():
    conn = sqlite3.connect('finans.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS cuzdan 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, tip TEXT, miktar REAL, maliyet REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ayarlar 
                   (anahtar TEXT PRIMARY KEY, deger REAL)''')
    varsayilanlar = [('f24k', 3000.0), ('f22k', 2800.0), ('fgms', 35.0), ('dolar', 33.0)]
    for anahtar, deger in varsayilanlar:
        conn.execute("INSERT OR IGNORE INTO ayarlar (anahtar, deger) VALUES (?,?)", (anahtar, deger))
    conn.commit()
    conn.close()

db_kur()

def fiyatlari_getir():
    conn = sqlite3.connect('finans.db')
    res = conn.execute("SELECT anahtar, deger FROM ayarlar").fetchall()
    conn.close()
    return dict(res)

fiyatlar = fiyatlari_getir()

# --- YAN PANEL (SOL MENÜ) ---
st.sidebar.title("⚙️ Kontrol Paneli")

st.sidebar.subheader("Fiyat Güncelleme")
with st.sidebar.form("fiyat_form"):
    f24k = st.number_input("🪙 24K ALTIN", value=float(fiyatlar.get('f24k', 3000)))
    f22k = st.number_input("💍 22K BİLEZİK", value=float(fiyatlar.get('f22k', 2800)))
    fgms = st.number_input("🥈 GÜMÜŞ", value=float(fiyatlar.get('fgms', 35)))
    dolar = st.number_input("💵 DOLAR", value=float(fiyatlar.get('dolar', 33.0)))
    fiyat_guncelle = st.form_submit_button("VERİLERİ GÜNCELLE 🔄")
    if fiyat_guncelle:
        conn = sqlite3.connect('finans.db')
        conn.execute("UPDATE ayarlar SET deger=? WHERE anahtar='f24k'", (f24k,))
        conn.execute("UPDATE ayarlar SET deger=? WHERE anahtar='f22k'", (f22k,))
        conn.execute("UPDATE ayarlar SET deger=? WHERE anahtar='fgms'", (fgms,))
        conn.execute("UPDATE ayarlar SET deger=? WHERE anahtar='dolar'", (dolar,))
        conn.commit()
        conn.close()
        st.rerun()

st.sidebar.subheader("➕ Varlık Yönetimi")
with st.sidebar.form("ekle_form"):
    tip = st.selectbox("Varlık Tipi", ["Altin (24K)", "Altin (22K - Bilezik)", "Gumus", "Vadeli Hesap (TL)", "Nakit (TL)"])
    # NEGATİF DEĞER GİRİŞİNE İZİN VERİLDİ (min_value kaldırıldı)
    miktar = st.number_input("Miktar", value=0.0, step=1.0)
    maliyet = st.number_input("Birim Maliyet", min_value=0.0, step=1.0)
    ekle_btn = st.form_submit_button("PORTFÖYE EKLE ✅")
    
    # Sıfır girilmediği sürece (+ veya -) veritabanına ekle
    if ekle_btn and miktar != 0:
        conn = sqlite3.connect('finans.db')
        conn.execute("INSERT INTO cuzdan (tarih, tip, miktar, maliyet) VALUES (?,?,?,?)", 
                     (datetime.now().strftime('%Y-%m-%d %H:%M'), tip, miktar, maliyet))
        conn.commit()
        conn.close()
        st.rerun()

st.sidebar.subheader("🗑️ Varlık Sil")
with st.sidebar.form("sil_form"):
    sil_id = st.number_input("Silinecek Varlık ID", min_value=0, step=1)
    sil_btn = st.form_submit_button("SİL")
    if sil_btn and sil_id > 0:
        conn = sqlite3.connect('finans.db')
        conn.execute("DELETE FROM cuzdan WHERE id=?", (sil_id,))
        conn.commit()
        conn.close()
        st.rerun()

# --- ANA EKRAN (DASHBOARD) ---
st.title("AKINCI FİNANS V10.5 - WEB DASHBOARD")

zaman_secimi = st.selectbox("⏱️ Zaman Filtresi", ["Tüm Zamanlar", "Günlük (24s)", "Haftalık", "Aylık", "1 Yıl"])

# Verileri Çekme ve Hesaplama
conn = sqlite3.connect('finans.db')
veriler = conn.execute("SELECT id, tarih, tip, miktar, maliyet FROM cuzdan").fetchall()
conn.close()

total_eder = 0
total_maliyet = 0
pasta_degerler = {}
pasta_karlar = {}
simdi = datetime.now()
tablo_verisi = []

for r in veriler:
    iid, tarih_db, v_tip, v_miktar, v_maliyet = r
    anapara = v_miktar * v_maliyet
    
    try:
        dt_obj = datetime.strptime(tarih_db, '%Y-%m-%d %H:%M')
    except ValueError:
        dt_obj = datetime.strptime(tarih_db.split()[0], '%Y-%m-%d')
    
    zaman_farki = simdi - dt_obj
    dahil = (zaman_secimi == "Tüm Zamanlar") or \
            (zaman_secimi == "Günlük (24s)" and zaman_farki <= timedelta(days=1)) or \
            (zaman_secimi == "Haftalık" and zaman_farki <= timedelta(days=7)) or \
            (zaman_secimi == "Aylık" and zaman_farki <= timedelta(days=30)) or \
            (zaman_secimi == "1 Yıl" and zaman_farki <= timedelta(days=365))

    if dahil:
        if "24K" in v_tip: gb = f24k
        elif "22K" in v_tip: gb = f22k
        elif "Gumus" in v_tip: gb = fgms
        elif "Vadeli" in v_tip:
            gun = (simdi - dt_obj).days + 1
            faiz = (anapara * (FAIZ_ORANI*(1-STOPAJ/100)/100) * (gun/365))
            gb = (anapara + faiz) / v_miktar if v_miktar != 0 else v_maliyet
        else: gb = v_maliyet

        g_toplam = v_miktar * gb
        
        if "Nakit" in v_tip:
            kar = g_toplam
            yuzde = 0.0
        else:
            kar = g_toplam - anapara
            yuzde = (kar / anapara * 100) if anapara != 0 else 0.0
            
        total_eder += g_toplam
        total_maliyet += anapara
        
        if g_toplam != 0:
            # Eksi girişleri grafikte netlemek (toplamak/çıkarmak) için
            pasta_degerler[v_tip] = pasta_degerler.get(v_tip, 0) + g_toplam
            pasta_karlar[v_tip] = pasta_karlar.get(v_tip, 0) + kar

        tablo_verisi.append({
            "ID": iid,
            "Tarih": dt_obj.strftime('%d.%m.%Y %H:%M'),
            "Varlık Tipi": v_tip,
            "Miktar": f"{v_miktar:.2f}",
            "Maliyet": f"{anapara:,.0f} ₺",
            "Güncel Değer": f"{g_toplam:,.0f} ₺",
            "Kar/Zarar": f"{kar:,.0f} ₺ (%{yuzde:.1f})"
        })

# --- ÖZET METRİKLERİ ---
total_net_kar = total_eder - total_maliyet
col1, col2, col3 = st.columns(3)
col1.metric(label=f"ANA PARA ({zaman_secimi})", value=f"{total_maliyet:,.0f} ₺")
col2.metric(label=f"PORTFÖY DEĞERİ ({zaman_secimi})", value=f"{total_eder:,.0f} ₺", delta=f"{total_net_kar:,.0f} ₺ Net Kar")
col3.metric(label=f"NET KAR YÜZDESİ ({zaman_secimi})", value=f"%{(total_net_kar / total_maliyet * 100) if total_maliyet > 0 else 0:.1f}")

st.divider()

# --- GRAFİKLER ---
if pasta_degerler:
    g_col1, g_col2 = st.columns(2)
    plt.style.use('dark_background')
    colors = ["#d29922", "#3fb950", "#58a6ff", "#f85149", "#8b949e"]

    # Sadece net değeri 0'dan büyük olanları (eksiye düşmeyenleri) grafiğe çiz
    aktif_degerler = {k: v for k, v in pasta_degerler.items() if v > 0}
    
    with g_col1:
        if aktif_degerler:
            fig1, ax1 = plt.subplots(figsize=(5, 3))
            fig1.patch.set_facecolor(DARK_BG)
            ax1.pie(aktif_degerler.values(), labels=aktif_degerler.keys(), autopct='%1.1f%%', colors=colors[:len(aktif_degerler)], startangle=140)
            ax1.set_title(f"Varlık Dağılımı ({zaman_secimi})", color="#3fb950", fontweight="bold")
            st.pyplot(fig1)
        else:
            st.info("Grafik oluşturulacak pozitif varlık bulunmuyor.")

    with g_col2:
        # Kar grafiği için büyüklükleri (abs) alıyoruz
        aktif_karlar = {k: abs(v) for k, v in pasta_karlar.items() if abs(v) > 0}
        if aktif_karlar:
            fig2, ax2 = plt.subplots(figsize=(5, 3))
            fig2.patch.set_facecolor(DARK_BG)
            ax2.pie(aktif_karlar.values(), labels=aktif_karlar.keys(), autopct='%1.1f%%', colors=colors[:len(aktif_karlar)], startangle=140)
            ax2.set_title(f"Kar/Zarar Analizi ({zaman_secimi})", color="#3fb950", fontweight="bold")
            st.pyplot(fig2)

st.divider()

# --- TABLO ---
st.subheader(f"📋 Portföy Detayları ({zaman_secimi})")
if tablo_verisi:
    df = pd.DataFrame(tablo_verisi)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info(f"Seçilen '{zaman_secimi}' filtresine uygun varlık bulunamadı.")
