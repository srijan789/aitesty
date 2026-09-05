const request = require('supertest');
const createApp = require('../src/app');
const { resetStore } = require('../src/store');

const app = createApp();

beforeEach(() => {
  resetStore();
});

describe('1. Create project (POST /api/projects)', () => {
  it('creates a project with valid data', async () => {
    const res = await request(app)
      .post('/api/projects')
      .send({ name: 'Website Redesign', description: 'Refresh the marketing site', deadline: '2026-12-01' });

    expect(res.status).toBe(201);
    expect(res.body.name).toBe('Website Redesign');
    expect(res.body.status).toBe('active');
    expect(res.body.progress).toEqual({ total: 0, completed: 0, progressPercent: 0 });
  });

  it('rejects a project without a name', async () => {
    const res = await request(app).post('/api/projects').send({ description: 'no name' });
    expect(res.status).toBe(400);
  });
});

describe('2. List projects (GET /api/projects)', () => {
  it('lists all created projects', async () => {
    await request(app).post('/api/projects').send({ name: 'Alpha' });
    await request(app).post('/api/projects').send({ name: 'Beta' });

    const res = await request(app).get('/api/projects');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(2);
  });

  it('filters projects by status', async () => {
    const created = await request(app).post('/api/projects').send({ name: 'Gamma' });
    await request(app).put(`/api/projects/${created.body.id}`).send({ status: 'completed' });
    await request(app).post('/api/projects').send({ name: 'Delta' });

    const res = await request(app).get('/api/projects?status=completed');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].name).toBe('Gamma');
  });
});

describe('3. Get project details (GET /api/projects/:id)', () => {
  it('returns a single project including its tasks and progress', async () => {
    const created = await request(app).post('/api/projects').send({ name: 'Onboarding' });

    const res = await request(app).get(`/api/projects/${created.body.id}`);
    expect(res.status).toBe(200);
    expect(res.body.name).toBe('Onboarding');
    expect(res.body.tasks).toEqual([]);
  });

  it('returns 404 for an unknown project', async () => {
    const res = await request(app).get('/api/projects/999999');
    expect(res.status).toBe(404);
  });
});

describe('4. Update project (PUT /api/projects/:id)', () => {
  it('updates project fields', async () => {
    const created = await request(app).post('/api/projects').send({ name: 'Old Name' });

    const res = await request(app)
      .put(`/api/projects/${created.body.id}`)
      .send({ name: 'New Name', status: 'completed' });

    expect(res.status).toBe(200);
    expect(res.body.name).toBe('New Name');
    expect(res.body.status).toBe('completed');
  });

  it('returns 404 when updating an unknown project', async () => {
    const res = await request(app).put('/api/projects/999999').send({ name: 'x' });
    expect(res.status).toBe(404);
  });

  // Edge case: clearing a deadline that was previously set. Editing a project to set a
  // *new* deadline always works, so this is easy to miss by clicking around -- but a
  // project manager naturally expects to be able to remove a deadline too.
  it('clears an existing deadline when it is set back to null', async () => {
    const created = await request(app)
      .post('/api/projects')
      .send({ name: 'Time-boxed Effort', deadline: '2026-01-01' });

    const res = await request(app)
      .put(`/api/projects/${created.body.id}`)
      .send({ deadline: null });

    expect(res.status).toBe(200);
    expect(res.body.deadline).toBeNull(); // fails: still returns '2026-01-01'
  });
});

describe('5. Delete project (DELETE /api/projects/:id)', () => {
  it('deletes an existing project', async () => {
    const created = await request(app).post('/api/projects').send({ name: 'Temp Project' });

    const del = await request(app).delete(`/api/projects/${created.body.id}`);
    expect(del.status).toBe(204);

    const getAfter = await request(app).get(`/api/projects/${created.body.id}`);
    expect(getAfter.status).toBe(404);
  });

  it('returns 404 when deleting an unknown project', async () => {
    const res = await request(app).delete('/api/projects/999999');
    expect(res.status).toBe(404);
  });
});

describe('6. Add task to a project (POST /api/projects/:id/tasks)', () => {
  it('adds a task to an existing project', async () => {
    const project = await request(app).post('/api/projects').send({ name: 'Launch Plan' });

    const res = await request(app)
      .post(`/api/projects/${project.body.id}/tasks`)
      .send({ title: 'Draft press release', assignee: 'Sam' });

    expect(res.status).toBe(201);
    expect(res.body.title).toBe('Draft press release');
    expect(res.body.completed).toBe(false);
  });

  it('returns 404 when the project does not exist', async () => {
    const res = await request(app).post('/api/projects/999999/tasks').send({ title: 'Orphan task' });
    expect(res.status).toBe(404);
  });
});

describe("7. Toggle a task's complete state (PATCH /api/projects/:id/tasks/:taskId/toggle)", () => {
  it('toggles a task from incomplete to complete and back', async () => {
    const project = await request(app).post('/api/projects').send({ name: 'Migration' });
    const task = await request(app)
      .post(`/api/projects/${project.body.id}/tasks`)
      .send({ title: 'Export data' });

    const toggled = await request(app).patch(
      `/api/projects/${project.body.id}/tasks/${task.body.id}/toggle`
    );
    expect(toggled.status).toBe(200);
    expect(toggled.body.completed).toBe(true);

    const toggledAgain = await request(app).patch(
      `/api/projects/${project.body.id}/tasks/${task.body.id}/toggle`
    );
    expect(toggledAgain.body.completed).toBe(false);
  });

  it("is reflected in the parent project's progress percentage", async () => {
    const project = await request(app).post('/api/projects').send({ name: 'Audit' });
    const task = await request(app)
      .post(`/api/projects/${project.body.id}/tasks`)
      .send({ title: 'Review logs' });
    await request(app).patch(`/api/projects/${project.body.id}/tasks/${task.body.id}/toggle`);

    const res = await request(app).get(`/api/projects/${project.body.id}`);
    expect(res.body.progress).toEqual({ total: 1, completed: 1, progressPercent: 100 });
  });
});

describe('8. Search projects by name (GET /api/projects/search)', () => {
  it('finds projects whose name matches a plain-word query', async () => {
    await request(app).post('/api/projects').send({ name: 'Website Redesign' });
    await request(app).post('/api/projects').send({ name: 'Mobile App' });

    const res = await request(app).get('/api/projects/search?q=website');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].name).toBe('Website Redesign');
  });

  it('finds projects whose name contains regex-special characters, e.g. "C++"', async () => {
    await request(app).post('/api/projects').send({ name: 'C++ Migration' });

    const res = await request(app).get('/api/projects/search?q=' + encodeURIComponent('C++'));

    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].name).toBe('C++ Migration');
  });
});
