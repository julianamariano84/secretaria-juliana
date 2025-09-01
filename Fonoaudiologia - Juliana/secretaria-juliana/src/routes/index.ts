import { Router } from 'express';
import AppointmentsController from '../controllers/appointmentsController';
import MessagesController from '../controllers/messagesController';
import ContactsController from '../controllers/contactsController';

const router = Router();

const appointmentsController = new AppointmentsController();
const messagesController = new MessagesController();
const contactsController = new ContactsController();

router.post('/appointments', appointmentsController.createAppointment.bind(appointmentsController));
router.get('/appointments/:id', appointmentsController.getAppointment.bind(appointmentsController));
router.put('/appointments/:id', appointmentsController.updateAppointment.bind(appointmentsController));
router.delete('/appointments/:id', appointmentsController.deleteAppointment.bind(appointmentsController));

router.post('/messages', messagesController.sendMessage.bind(messagesController));
router.get('/messages/:id', messagesController.getMessage.bind(messagesController));

router.post('/contacts', contactsController.addContact.bind(contactsController));
router.get('/contacts/:id', contactsController.getContact.bind(contactsController));

export default router;