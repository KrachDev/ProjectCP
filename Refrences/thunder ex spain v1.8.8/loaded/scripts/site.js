
function GetW(w) {
    return $(window).width() > w ? w : $(window).width() - 30;
}
function GetH(h) {
    return $(window).height() > h ? h : $(window).height() - 30;
}
var ShowError = function (error) {
    $(".validation-summary").html(error);
    $(".validation-summary").css("display", "block")
}
var HideError = function () {
    $(".validation-summary").html('');
    $(".validation-summary").css("display", "none")
}
function ShowLoader() {
    document.getElementById("global-overlay").style.display = "block";
}
function HideLoader() {
    document.getElementById("global-overlay").style.display = "none";
}
function OpenPopup(url, winProp) {
    var win = GetMainWindow();
    win.iframeOpenUrl = url
    win.OpenWindow(winProp);
    return false;
}
function BackToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth',
    });
}
function OpenWindow(winProp) {

    var obj = eval(globalPopups.peek());
    if (winProp.Reload == true) {
    }
    else if (winProp.Refresh == true) {
        if (obj !== null) {
            iframeOpenUrl = obj.Url;
        }
    }
    else {
        if (obj === null) {
            winProp.Id = 1;
            winProp.Url = iframeOpenUrl;
            obj = winProp;
            globalPopups.push(winProp);
        }
        else {
            winProp.Id = eval(obj.Id) + 1;
            winProp.Url = iframeOpenUrl;
            obj = winProp;
            globalPopups.push(winProp);
        }
    }
    var name = "popup_" + obj.Id;
    var wnd = $("#" + name).data("kendoWindow");

    if (wnd) {
        var h = $(window).height();
        var w = $(window).width();
        if (h < eval(winProp.Height) || w < eval(winProp.Width)) {
            wnd.setOptions({
                title: winProp.Title
            });
            wnd.maximize().refresh({ url: iframeOpenUrl });
        }
        else {
            wnd.setOptions({
                width: winProp.Width,
                height: winProp.Height,
                title: winProp.Title
            });
            wnd.refresh({ url: iframeOpenUrl });
        }

        if (globalWindowSender != null) {
            kendo.ui.progress(globalWindowSender.sender.element, true);
        }
        return false;

    } else {
        wnd = $("<div id='" + name + "'></div>").kendoWindow({
            title: winProp.Title,
            width: winProp.Width,
            iframe: true,
            resizable: true,
            actions: ["Maximize", "Close"],
            height: winProp.Height,
            modal: true,
            open: OnWindowOpen,
            activate: OnWindowActivate,
            close: OnWindowClose,
            deactivate: OnWindowDeactivate,
            refresh: OnWindowRefresh,

            visible: true
        }).data("kendoWindow");
        var h = $(window).height();
        var w = $(window).width();
        if (h < eval(winProp.Height) || w < eval(winProp.Width)) {
            wnd.center();//.maximize();
        }
        else {
            wnd.center();
        }
    }
}
function RemoveMultipleOverlays() {
    $('div.k-overlay').remove();
}
function CloseWindow(cb) {
    globalCallBack = cb;
    var obj = globalPopups.peek();
    if (obj === null) {
        return null;
    }
    var name = "popup_" + obj.Id;
    var wnd = $("#" + name).data("kendoWindow");
    if (wnd != null) {
        wnd.close();
    }
    return false;
}
function GetMainWindow(win) {
    if (win === null || win === undefined) {
        win = window;
    }
    if (win.frameElement === null || win.frameElement === undefined) {
        return win;
    }
    return GetMainWindow(win.parent);
}
function GetWindow() {
    var obj = globalPopups.peek();

    if (obj === null) {
        return null;
    }
    var name = "popup_" + obj.Id;
    var windowElement = $("#" + name);
    var iframeDomElement = windowElement.children("iframe")[0];
    var iframeWindowObject = iframeDomElement.contentWindow;
    return iframeWindowObject;
}
function GetParentWindow() {
    var obj = globalPopups.peek(1);
    if (obj === null) {
        return window;
    }
    var name = "popup_" + obj.Id;
    var windowElement = $("#" + name);
    var iframeDomElement = windowElement.children("iframe")[0];
    var iframeWindowObject = iframeDomElement.contentWindow;
    return iframeWindowObject;
}
function OnWindowActivate(e) {
    var obj = globalPopups.peek();
    if (obj === null) {
        return null;
    }
    var name = "popup_" + obj.Id;
    var wnd = $("#" + name).data("kendoWindow");
    wnd.refresh({
        url: iframeOpenUrl,
        cache: false,
        type: "GET"
    });
    globalWindowSender = e;
    kendo.ui.progress(e.sender.element, true);
}
function OnWindowOpen(e) {
}
function OnWindowClose(e) {

}
function OnWindowRefresh(e) {
    kendo.ui.progress(e.sender.element, false);
}
function OnWindowDeactivate(e) {

    var obj = globalPopups.pop();
    if (obj === null) {
        return null;
    }
    var name = "popup_" + obj.Id;
    var wnd = $("#" + name).data("kendoWindow");
    wnd.content("");
    wnd.destroy();
    if (globalCallBack !== null && globalCallBack !== undefined) {
        win = GetWindow();
        if (win === null || win === undefined) {
            win = window;
        }
        if (globalCallBack.IframeName !== null && globalCallBack.IframeName !== undefined) {
            var iframe_object = win.document.getElementById(globalCallBack.IframeName);
            if (iframe_object !== null && iframe_object.contentWindow) {
                win = iframe_object.contentWindow;
            }
        }
        //GetIframeOrWindow('IFrameForPrepareVacancyList_iframe');
        win[globalCallBack.MethodName](globalCallBack.Prms);
        globalCallBack = null;
    }

}


var onAjaxBegin = function () {
    ShowLoader();
    //ShowLoader();

};

var onAjaxComplete = function () {
    HideLoader();
};
var onAjaxFailed = function (context, res) {
    if (context.status === 400 || context.status === 403) {
        alert('Your session has been expired. Please try again');
        window.location.href = window.location.href;
    }
    else {
        //alert('An un expected error occured. Please try again later');
        //window.location.href = window.location.href;
    }
};
var showError = function (error) {
    $("#validation-summary").html(error);
    $("#validation-summary").css("display", "block");
}

function GetStack() {
    return new Stack();
}
window.OnPhotoError = (obj) => {
    obj.onerror = null;
    obj.src = '~/assets/images/avatar/01.jpg';

};
class Stack {

    constructor() {
        this.items = [];
    }

    push(element) {
        this.items.push(element);
    }
    pop() {
        if (this.items.length == 0)
            return null;
        return this.items.pop();
    }
    peek(index) {
        if (index === null || index === undefined) {
            index = 0;
        }
        if (this.items.length <= index)
            return null;
        return this.items[this.items.length - index - 1];
    }
    isEmpty() {
        return this.items.length == 0;
    }
}
