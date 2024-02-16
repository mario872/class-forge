function showHide(elementID) {
    element = document.getElementById(elementID);
    if (element.classList.contains('hidden')) {
        element.classList.remove('hidden');
    } else {
        element.classList.add('hidden');
    }
  }