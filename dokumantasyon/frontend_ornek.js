
async function haberleriGetir() {
    try {
        const response = await fetch("http://localhost:8000/news");
        const haberler = await response.json();

        console.log("Haberler Geldi:", haberler);

        haberler.forEach(haber => {
            console.log(`Başlık: ${haber.title}`);
            console.log(`Resim: ${haber.image}`);
        });

    } catch (error) {
        console.error("Hata oluştu:", error);
    }
}

async function teknolojiHaberleriGetir() {
    const response = await fetch("http://localhost:8000/news?category=teknoloji");
    const teknolojiHaberleri = await response.json();
    return teknolojiHaberleri;
}

haberleriGetir();
