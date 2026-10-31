from zeep import Client
c = Client("http://v2haproxy_vip.wneweb.com.tw:100/sfcs_webservice/ats.asmx?WSDL")
for svc in c.wsdl.services.values():
    for port in svc.ports.values():
        for name, op in sorted(port.binding._operations.items()):
            print(name, "|", op.input.signature(), "->", op.output.signature())