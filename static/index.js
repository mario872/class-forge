function showHide(elementID) {
    let element = document.getElementById(elementID);
    console.log(element);
    if (element.classList.contains('hidden')) {
        element.classList.remove('hidden');
    } else {
        element.classList.add('hidden');
    }
  }

function elementAppend(elementID, text, secondaryElement=null) {
    let element = document.getElementById(elementID);
    if (secondaryElement != null) {
        secondaryElement = document.getElementById(secondaryElement).classList.contains('hidden');
    } else {
        secondaryElement = false;
    }
    if (! element.innerText.includes(text) && secondaryElement) {
        element.innerText += text;
    }
}

function elementRemove(elementID, text) {
    let element = document.getElementById(elementID);
    element.innerText = element.innerText.replace(text, '')
}

function elementReplace(elementID, orginalText, newText) {
    let element = document.getElementById(elementID);
    element.innterText = element.innerText.replace(orginalText, newText)
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