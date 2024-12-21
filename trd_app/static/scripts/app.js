$(document).ready(function() {
    $('form').each(function () {
        $(this).submit(function (e) {
            e.preventDefault();
        })
    })
    bootstrapFormat();
    setTimeout(set_estr_prm,200);

})

function bootstrapFormat()
{
    $('table.table-dg').addClass('table')
    $('table.table-dg').addClass('table-hover')
    $('table.table-dg thead th').addClass('fw-light')
    $('table.table-dg thead th').css('background-color','#162124')
    
    $('table.table-trade-info').addClass('table-sm')
    $('table.table-trade-info').addClass('table-borderless')
    $('table.table-trade-info tbody tr.red').find('td').addClass('text-danger');
    $('table.table-trade-info tbody tr.green').find('td').addClass('text-success');
    $('table.table-trade-info').css('font-family','var(--bs-font-monospace)');
    $('table.table-trade-info').css('font-size','0.8em');

}

function to_dec(x,n)
{
    x = parseFloat(x);
    return x.toFixed(n);
}

/**
 * 
 * @param {*} url '{% url "url_name" %}'
 * @param {*} data {
                    data_a: $('#data_a').val(),
                    data_b: $('#data_b').val(),
                }
 */
var ajxRsp;
function get_ajax(url,data) {
    spinner_show();
    if (data)
    {
        data.csrfmiddlewaretoken = $('input[name=csrfmiddlewaretoken]').val();
        data.action =  'post';
    }
    else
    {
        data = {
            csrfmiddlewaretoken: $('input[name=csrfmiddlewaretoken]').val(),
            action: 'post',
        }        
    }
    return $.ajax({
        type: 'POST',
        url: url,
        data: data,
        error: function (xhr, errmsg, err) {
            //console.log(xhr.status + ": " + xhr.responseText); 
            console.log(xhr.status + "\n" + errmsg+ "\n" + err); 
        }
    }).done(function () {
        bootstrapFormat();
        spinner_hide();
    });
}

function spinner_show()
{
    $('#ajax_spinner').show();
}

function spinner_hide()
{
    $('#ajax_spinner').hide();
}

function html_alert(title, text, cls) {
    var html = '<span class="' + cls + '">' + text + '</span>';
    $('#html_alert_title').html(title)
    $("#html_alert_body").html(html);
    $('#html_alert').show();
}

window.alert = function(msg,el,isError) {
    var cls = 'text-primary';
    if (isError)
        var cls = 'text-danger';
    html_alert('Alerta!',msg,cls);
    return;
}

function set_estr_prm()
{
    $('.estr_prm').each( function () {
        var type = $(this).attr('data-type');
        var id = $(this).attr('id')
        
        if (type=='int')
        {
            $(this).attr('type','number');
            $(this).attr('step','1');
            $(this).attr('onkeypress','return event.charCode >= 48 && event.charCode <= 57');
        }
        if (type=='dec' || type== 'perc')
        {
            $(this).attr('type','number');
        }

        $(this).on('change',function () {

            estrategia_prm_valid(id);
        });
    })
}

function estrategia_prm_valid(id)
{
    var input = $('#'+id);
    value = input.val();
    type = input.attr('data-type');
    limit = input.attr('data-limit');
    descripcion = input.attr('data-descripcion');
    
    if (value && limit)
    {
        if (!validarNIntervalo(value,limit))
        {
            if (type == 'int')
            {
                alert('En el campo '+descripcion+' se debe ingresar un numero entero con los siguientes limites '+limit);
                input.focus();
            }
            if (type == 'dec' || type== 'perc')
            {
                alert('En el campo '+descripcion+' se debe ingresar un numero con los siguientes limites '+limit);
                input.val('');
                input.focus();
            }
            return false;
        }
    }
    return true;
}

function validarNIntervalo(valor, intervalo) {
    // Expresión regular para detectar los límites del intervalo
    const regex = /^([\(\[])(-?\d+\.?\d*),(-?\d+\.?\d*)([\)\]])$/;
    const match = intervalo.match(regex);

    if (!match) {
        console.log("Intervalo mal formado. "+intervalo);
        return false;
    }

    const [, inicioTipo, inicio, fin, finTipo] = match;

    // Convertir los límites a números
    const inicioNum = parseFloat(inicio);
    const finNum = parseFloat(fin);
    const numero = parseFloat(valor);

    if (isNaN(numero)) {
        return false; // El valor no es un número
    }

    // Validar según el tipo de intervalo
    const esValido =
        (inicioTipo === "[" ? numero >= inicioNum : numero > inicioNum) &&
        (finTipo === "]" ? numero <= finNum : numero < finNum);

    return esValido;
}