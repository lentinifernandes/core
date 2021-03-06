# !/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
ERP+
"""
__author__ = 'António Anacleto'
__credits__ = []
__version__ = "1.0"
__maintainer__ = "António Anacleto"
__status__ = "Development"
__model_name__= 'prato.Prato'
import auth, base_models
from orm import *
from form import *
try:
    from my_produto import Produto
except:
    from produto import Produto

class Prato(Model, View):
    def __init__(self, **kargs):
        Model.__init__(self, **kargs)
        self.__name__ = 'prato'
        self.__title__= 'Produção de Pratos'
        self.__model_name__ = __model_name__
        self.__list_edit_mode__ = 'edit'
        self.__workflow__ = (
            'estado', {'Rascunho':['Confirmar'], 'Confirmado':['Imprimir', 'Cancelar'], 'Impresso':['Cancelar', 'Imprimir'], 'Cancelado':[]}
            )
        self.__workflow_auth__ = {
            'Confirmar':['Vendedor'],
            'Imprimir':['All'],
            'Facturar':['Vendedor'],
            'Cancelar':['Vendedor'],
            'full_access':['Gestor']
            }
        self.__tabs__ = [
            ('Componentes do Prato', ['linha_prato']),
            ('Movimentos', ['movs_contab', 'movs_stock']),
            ]
        self.__no_edit__ = [
            ('estado', ['Confirmado','Impresso','Cancelado'])
            ]
        self.__auth__ = {
            'read':['All'],
            'write':['Vendedor'],
            'create':['Vendedor'],
            'delete':['Gestor'],
            'full_access':['Gestor']
            }
        self.__get_options__ = ['numero']

        self.data = date_field(view_order=1, name ='Data', args='required', default=datetime.date.today())
        self.numero = info_field(view_order=2, name ='Número', args='readonly')
        self.produto = choice_field(view_order=3, name ='Produto', args='required tabIndex="-1"', size=55, model='produto', column='nome', options='model.get_produtos()')
        self.doses = decimal_field(view_order=4, name ='Doses Prod.', size=15, sum=True, onchange='valores_onchange', default=1.0)
        self.notas = string_field(view_order=5, name ='Notas', args='autocomplete="on"', size=80, onlist=False, search=False)
        self.estado = info_field(view_order=6, name ='Estado', default='Rascunho', search=False)# dynamic_atrs='estado_dyn_attrs',
        self.movs_stock = list_field(view_order=7, name ='Movimentos Stock', condition="documento='prato' and num_doc={numero}", model_name='stock.Stock', list_edit_mode='edit', onlist = False)
        self.linha_prato = list_field(view_order=8, name ='Linhas de Prato', condition="prato='{id}'", model_name='linha_prato.LinhaPrato', list_edit_mode='inline', onlist = False)

    def get_produtos(self):
        return Produto().get_options_sellable()

    def estado_dyn_attrs(self, value):
        # permite devolver atributos dinamicos ou seja atributos html que mudam consoante por exemplo valores de certos campos
        result = {}
        #if value == 'Rascunho':
        #   result = {'total':'hidden', 'data':'hidden'}
        #elif value in ['Confirmado','Facturado']:
        #   result = {'total':'disabled', 'data':'disabled'}
        return result

    def get_total(self, key):
        from linha_prato import LinhaPrato
        value = to_decimal(0)
        record_lines = LinhaPrato(where="prato = '{prato}'".format(prato=key)).get()
        if record_lines:
            for line in record_lines:
                value += to_decimal(line['valor_total'])
        return round(value,0)

    def Imprime(self, key, window_id):
        #Acção por defeito para imprimir o documento base
        #Deverá mudar o estado para impresso
        from linha_prato import LinhaPrato
        record_id = key
        record = model.get(key=record_id)[0]
        record['user'] = session['user']
        record['estado'] = 'Impresso'
        record_lines = run_sql("SELECT linha_prato.*, produto.nome as nome_produto FROM linha_prato JOIN produto on produto.id = linha_prato.produto WHERE prato = '{prato}'".format(prato=record['id']))
        from subprocess import Popen,PIPE
        lpr = Popen(["/usr/bin/lpr", "-P", "bar"], stdin=PIPE, shell=False, stdout=PIPE, stderr=PIPE)
        printDoc = ''
        OpenDraw=chr(27) + chr(112) + chr(0) + chr(32) + chr(32)
        Now = time.strftime("%X")
        Today = datetime.date.today()
        Line = '----------------------------------------' + '\n'
        LineAdvance=chr(27) + chr(100) + chr(5)
        StartPrinter=chr(27)+ chr(61) + chr(1) + chr(27) + chr(64) + chr(27) + "" + chr(0) + chr(27)+ chr(73) + chr(0)
        CutPaper=chr(27) + chr(86) + chr(0)
        printDoc += '{today:21} Prato n.:{number:>8}\n'.format(today=str(Today), number=str(record['numero']))
        printDoc += Now + '\n'
        printDoc += 'Funcionario: {funcionario}\n'.format(funcionario=record['funcionario'])
        printDoc += 'Produzidos {doses} {produto} \n'.format(prato=record['produto'], doses=record['doses'])
        printDoc += Line
        total = to_decimal('0')
        for item in record_lines:
            description=item['nome_produto']
            quantity=str(int(item['quantidade']))
            value=str(item['valor_total'])
            total += to_decimal(value)
            printDoc += '{description:<25} {quantity:>5} {value:>8}\n'.format(description=description, quantity=quantity, value=value)
        printDoc += Line
        printDoc += 'Total: {total:>33}\n'.format(total=str(total))
        printDoc += Line + LineAdvance + LineAdvance + CutPaper
        lpr.communicate(printDoc.encode("utf-8"))
        Prato(**record).put()
        return form_edit(key = key, window_id = window_id)

    def Confirmar(self, key, window_id):
        #ainda não esta 100% ver com calma outro dia
        # Gera movimento contabilistico (conta de materias primas contra conta de gastos e entrada de produto acabado em armazem)
        # Gera movimento de Stock (sai materia prima do armazem por contrapartida de produto acabado)
        if key in ['None', None]:
            key = get_actions(action='save', key=None, model_name=model.__model_name__, internal=True)
        record_id = key
        record = model.get(key=record_id)[0]
        record['user'] = session['user']
        record['estado'] = 'Confirmado'
        record['numero'] = base_models.Sequence().get_sequence('prato')
        from diario import Diario
        diario = Diario(where="tipo='stock'").get()[0]['id']
        periodo = None
        from periodo import Periodo
        periodos = Periodo().get()
        for p in periodos:
            lista_datas = generate_dates(start_date=p['data_inicial'], end_date=p['data_final'])
            if str(format_date(record['data'])) in lista_datas:
                periodo = p['id']
        if not periodo:
            return error_message('não existe periodo definido para a data em questão! \n')
        from armazem import Armazem
        armazem_cliente = Armazem(where="tipo='cliente'").get()[0]['id']
        from movimento import Movimento
        movimento = Movimento(data=record['data'], numero=base_models.Sequence().get_sequence('movimento'), num_doc=record['numero'], descricao='Nossa Guia de Produção', diario=diario, documento='prato', periodo=periodo, estado='Confirmado', user=session['user'], active=False).put()
        from stock import Stock
        stock = Stock(data=record['data'], numero=base_models.Sequence().get_sequence('stock'), num_doc=record['numero'], descricao='Nossa Guia de Produção', documento='prato', periodo=periodo, estado='Confirmado', user=session['user']).put()
        Prato(**record).put()
        from linha_prato import LinhaPrato
        record_lines = LinhaPrato(where="prato = '{prato}'".format(prato=record['id'])).get()
        if record_lines:
            from linha_movimento import LinhaMovimento
            from linha_stock import LinhaStock
            from produto import Produto
            from familia_produto import FamiliaProduto
            for line in record_lines:
                # tambem depois considerar a verificação se o total está bem calculado e logs se o preço unitário for modificado
                quantidade = to_decimal(line['quantidade'])
                product = Produto().get(key=line['produto'])[0]
                conta_mercadorias = product['conta_mercadorias']
                conta_gastos = product['conta_gastos']
                taxa_iva = product['iva']
                armazem_vendas = None
                familia = FamiliaProduto().get(key=product['familia'])
                if familia:
                    familia = familia[0]
                    if familia['armazem_vendas']:
                        armazem_vendas = familia['armazem_vendas']
                descricao = product['nome']
                #total_sem_iva = line['valor_total']/(1+taxa_iva)
                #Aqui ver a contabilização
                LinhaMovimento(movimento=movimento, descricao=descricao, conta=conta_gastos, quant_debito=quantidade, debito=line['valor_total'], quant_credito=to_decimal(0), credito=to_decimal(0), user=session['user']).put()
                LinhaMovimento(movimento=movimento, descricao=descricao, conta=conta_mercadorias, quant_debito=to_decimal(0), debito=to_decimal(0), quant_credito=quantidade, credito=line['valor_total'], user=session['user']).put()
                # o movimento é no armazem cozinha e sai materia-prima entra produto acabado
                LinhaStock(stock=stock, descricao=descricao, produto=line['produto'], armazem=armazem_materia_prima, quant_saida=quantidade, quant_entrada=0.0, user=session['user']).put()
                LinhaStock(stock=stock, descricao=descricao, produto=line['produto'], armazem=armazem_produto, quant_saida=0.0, quant_entrada=quantidade, user=session['user']).put()
            return form_edit(key = key, window_id = window_id)
        else:
            return error_message('Não pode confirmar talões sem linhas de Talão! \n')

    def Cancelar(self, key, window_id):
        # Estorna movimento contabilistico
        # Estorna movimento de stock
        record_id = key
        record = model.get(key=record_id)[0]
        record['user'] = session['user']
        record['estado'] = 'Cancelado'
        from movimento import Movimento
        from linha_movimento import LinhaMovimento
        movimentos = Movimento(where="documento='prato'and num_doc={num_doc} ".format(num_doc=record['numero'])).get()
        if movimentos:
            for movimento in movimentos:
                new_movimento = {}
                new_movimento['user'] = session['user']
                for key in movimento.keys():
                    if key not in ['id', 'user_create', 'user_change', 'date_create', 'date_change','numero','descricao']:
                        new_movimento[key] = movimento[key]
                new_movimento['numero'] = base_models.Sequence().get_sequence('movimento')
                new_movimento['descricao'] = 'Anulação de ' + movimento['descricao']
                new_movimento_id = Movimento(**new_movimento).put()
                linhas_movimento = LinhaMovimento(where="movimento='{movimento}'".format(movimento=movimento['id'])).get()
                for linhamovimento in linhas_movimento:
                    new_linha_movimento = {}
                    new_quant_debito = to_decimal(0)
                    new_quant_credito = to_decimal(0)
                    new_debito = to_decimal(0)
                    new_credit = to_decimal(0)
                    for key in linhamovimento.keys():
                        if key not in ['id', 'user_create', 'user_change', 'date_create', 'date_change','movimento']:
                            if key == 'quant_debito':
                                new_quant_credito = linhamovimento[key]
                            elif key == 'quant_credito':
                                new_quant_debito = linhamovimento[key]
                            elif key == 'credito':
                                new_debito = linhamovimento[key]
                            elif key == 'debito':
                                new_credito = linhamovimento[key]
                            else:
                                new_linha_movimento[key] = linhamovimento[key]
                    new_linha_movimento['movimento'] = new_movimento_id
                    new_linha_movimento['quant_debito'] = new_quant_debito
                    new_linha_movimento['quant_credito'] = new_quant_credito
                    new_linha_movimento['debito'] = new_debito
                    new_linha_movimento['credito'] = new_credito
                    new_linha_movimento['user'] = session['user']
                    LinhaMovimento(**new_linha_movimento).put()
        from stock import Stock
        from linha_stock import LinhaStock
        stocks = Stock(where="documento='prato'and num_doc={num_doc} ".format(num_doc=record['numero'])).get()
        if stocks:
            for stock in stocks:
                new_stock = {}
                new_stock['user'] = session['user']
                for key in stock.keys():
                    if key not in ['id', 'user_create', 'user_change', 'date_create', 'date_change','numero']:
                        new_stock[key] = stock[key]
                new_stock['numero'] = base_models.Sequence().get_sequence('stock')
                new_stock['descricao'] = 'Anulação de ' + stock['descricao']
                new_stock_id = Stock(**new_stock).put()
                linhas_stock = LinhaStock(where="stock={stock}".format(stock=stock['id'])).get()
                for linhastock in linhas_stock:
                    new_linha_stock = {}
                    new_quant_entrada = to_decimal(0)
                    new_quant_saida = to_decimal(0)
                    for key in linhastock.keys():
                        if key not in ['id', 'user_create', 'user_change', 'date_create', 'date_change','stock']:
                            if key == 'quant_entrada':
                                new_quant_saida = linhastock[key]
                            elif key == 'quant_saida':
                                new_quant_entrada = linhastock[key]
                            else:
                                new_linha_stock[key] = linhastock[key]
                    new_linha_stock['stock'] = new_stock_id
                    new_linha_stock['quant_entrada'] = new_quant_entrada
                    new_linha_stock['quant_saida'] = new_quant_saida
                    new_linha_stock['user'] = session['user']
                    LinhaStock(**new_linha_stock).put()
        Prato(**record).put()
        return form_edit(key = 'None', window_id = window_id)
