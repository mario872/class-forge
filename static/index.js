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