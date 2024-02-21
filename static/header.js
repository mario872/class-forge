function headerShowHide(elementID) {
    let element = document.getElementById(elementID);
    if (element.classList.contains('hidden')) {
        element.classList.remove('hidden');
    } else {
        element.classList.add('hidden');
    }
  }

function fetch_timetable_css(elementID) {
    let element = document.getElementById(elementID);
    element.disabled = true;
    element.innerText = 'Fetching...';
    const classes = ['from-blue-500', 'via-blue-600', 'to-blue-700'];
    for (class_id in classes) {
        element.classList.remove(class_id)
    }
    element.classList.add('blue-500')
}