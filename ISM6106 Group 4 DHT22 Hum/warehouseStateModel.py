from StateModel import StateModel
STATE_NORMAL  = 0
STATE_WARNING = 1
STATE_ALARM   = 2
class WarehouseStateMachine:
    
    def __init__(self, handler, debug=False):

        self.model = StateModel(3, handler, debug)

        # DEFINE CUSTOM EVENTS (Necessary to prevent "ValueError: Invalid event X")
        self.model.addCustomEvent("temp_warning")
        self.model.addCustomEvent("temp_alarm")
        self.model.addCustomEvent("reset_event")

        # DEFINE TRANSITIONS (Centralized logic)
        self.model.addTransition(STATE_NORMAL,  ['temp_warning'], STATE_WARNING)
        self.model.addTransition(STATE_NORMAL,  ['temp_alarm'],     STATE_ALARM)
        self.model.addTransition(STATE_WARNING, ['temp_alarm'],     STATE_ALARM)
        self.model.addTransition(STATE_ALARM, ['reset_event'], STATE_NORMAL)

