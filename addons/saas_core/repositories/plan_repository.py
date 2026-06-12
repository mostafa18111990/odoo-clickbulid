class PlanRepository:
    def __init__(self, env):
        self.env = env
        self._model = env['saas.plan']

    def find_all_active(self):
        return self._model.search([('active', '=', True)], order='monthly_price asc')

    def find_by_code(self, code):
        return self._model.search([('code', '=', code)], limit=1)

    def find_by_id(self, plan_id):
        return self._model.browse(plan_id).exists()

    def find_recommended(self):
        return self._model.search([('active', '=', True), ('is_recommended', '=', True)], limit=1)

    def find_popular(self):
        return self._model.search([('active', '=', True), ('is_popular', '=', True)])
