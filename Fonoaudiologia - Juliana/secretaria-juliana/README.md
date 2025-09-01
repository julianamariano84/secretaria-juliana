# Secretaria Juliana - Fonoaudióloga Infantil

Este projeto é uma aplicação de gerenciamento de atendimentos para Juliana Mariano, uma fonoaudióloga especializada em atendimento infantil. A aplicação integra-se com o WhatsApp Business através da plataforma Z-API, permitindo a comunicação eficiente com os clientes.

## Estrutura do Projeto

- **src/**: Contém o código-fonte da aplicação.
  - **app.ts**: Ponto de entrada da aplicação, inicializa o servidor Express e configura as rotas.
  - **controllers/**: Controladores que gerenciam as requisições.
    - **appointmentsController.ts**: Gerencia as requisições relacionadas a agendamentos.
    - **messagesController.ts**: Gerencia o envio e recebimento de mensagens via WhatsApp.
    - **contactsController.ts**: Gerencia informações de contatos.
  - **services/**: Contém a lógica de negócios.
    - **zapiService.ts**: Comunicação com a Z-API.
    - **appointmentService.ts**: Lógica relacionada a agendamentos.
    - **messageService.ts**: Lógica para manipulação de mensagens.
  - **integrations/**: Integrações com serviços externos.
    - **zapi/**: Integração com a Z-API.
  - **routes/**: Configuração das rotas da aplicação.
  - **models/**: Modelos de dados.
  - **config/**: Configurações da aplicação.
  - **utils/**: Funções utilitárias.
  - **types/**: Tipos e interfaces TypeScript.

- **tests/**: Contém os testes da aplicação.
  - **integration/**: Testes de integração.
  
- **.env.example**: Exemplo de variáveis de ambiente necessárias para configuração.
- **package.json**: Configuração do npm, incluindo dependências e scripts.
- **tsconfig.json**: Configuração do TypeScript.

## Instalação

1. Clone o repositório:
   ```
   git clone <URL_DO_REPOSITORIO>
   cd secretaria-juliana
   ```

2. Instale as dependências:
   ```
   npm install
   ```

3. Renomeie o arquivo `.env.example` para `.env` e configure as variáveis de ambiente conforme necessário.

4. Inicie a aplicação:
   ```
   npm start
   ```

## Uso

A aplicação permite que Juliana gerencie agendamentos, envie mensagens e mantenha um registro de contatos através do WhatsApp. As funcionalidades incluem:

- Agendar atendimentos.
- Enviar e receber mensagens via WhatsApp.
- Gerenciar informações de contato.

## Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## Licença

Este projeto está licenciado sob a MIT License. Veja o arquivo LICENSE para mais detalhes.