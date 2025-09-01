import { Appointment } from '../models/appointment';

export class AppointmentService {
    private appointments: Appointment[] = [];

    public scheduleAppointment(appointment: Appointment): Appointment {
        this.appointments.push(appointment);
        return appointment;
    }

    public getAppointments(): Appointment[] {
        return this.appointments;
    }

    public updateAppointment(id: string, updatedAppointment: Appointment): Appointment | null {
        const index = this.appointments.findIndex(app => app.id === id);
        if (index !== -1) {
            this.appointments[index] = { ...this.appointments[index], ...updatedAppointment };
            return this.appointments[index];
        }
        return null;
    }

    public cancelAppointment(id: string): boolean {
        const index = this.appointments.findIndex(app => app.id === id);
        if (index !== -1) {
            this.appointments.splice(index, 1);
            return true;
        }
        return false;
    }
}