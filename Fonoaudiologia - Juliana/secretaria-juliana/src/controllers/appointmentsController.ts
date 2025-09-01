import { Request, Response } from 'express';
import { AppointmentService } from '../services/appointmentService';

export class AppointmentsController {
    private appointmentService: AppointmentService;

    constructor() {
        this.appointmentService = new AppointmentService();
    }

    public async createAppointment(req: Request, res: Response): Promise<void> {
        try {
            const appointmentData = req.body;
            const newAppointment = await this.appointmentService.createAppointment(appointmentData);
            res.status(201).json(newAppointment);
        } catch (error) {
            res.status(500).json({ message: 'Error creating appointment', error });
        }
    }

    public async updateAppointment(req: Request, res: Response): Promise<void> {
        try {
            const appointmentId = req.params.id;
            const appointmentData = req.body;
            const updatedAppointment = await this.appointmentService.updateAppointment(appointmentId, appointmentData);
            res.status(200).json(updatedAppointment);
        } catch (error) {
            res.status(500).json({ message: 'Error updating appointment', error });
        }
    }

    public async getAppointment(req: Request, res: Response): Promise<void> {
        try {
            const appointmentId = req.params.id;
            const appointment = await this.appointmentService.getAppointment(appointmentId);
            if (appointment) {
                res.status(200).json(appointment);
            } else {
                res.status(404).json({ message: 'Appointment not found' });
            }
        } catch (error) {
            res.status(500).json({ message: 'Error retrieving appointment', error });
        }
    }

    public async getAllAppointments(req: Request, res: Response): Promise<void> {
        try {
            const appointments = await this.appointmentService.getAllAppointments();
            res.status(200).json(appointments);
        } catch (error) {
            res.status(500).json({ message: 'Error retrieving appointments', error });
        }
    }
}