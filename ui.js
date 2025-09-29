function showPage(pageId) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    const newPage = document.getElementById(pageId);
    if (newPage) {
        newPage.classList.add('active');
        newPage.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}
