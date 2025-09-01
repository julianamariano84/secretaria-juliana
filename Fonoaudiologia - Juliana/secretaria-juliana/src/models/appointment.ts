export class Appointment {
    constructor(
        public id: string,
        public clientName: string,
        public date: Date,
        public time: string,
        public notes?: string
    ) {}
}