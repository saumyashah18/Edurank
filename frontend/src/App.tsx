import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AuthPage } from './pages/AuthPage';
import { Dashboard } from './pages/Dashboard';
import { ProfessorDashboard } from './pages/ProfessorDashboard';
import { ManageAssessment } from './pages/ManageAssessment';
import { StudentEntry } from './pages/StudentEntry';
import { StudentQuiz } from './pages/StudentQuiz';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/professor/create" element={<ProfessorDashboard />} />
          <Route path="/professor/manage/:quizId" element={<ManageAssessment />} />
          <Route path="/student/quiz/:quizId" element={<StudentEntry />} />
          <Route path="/student/quiz/:quizId/active" element={<StudentQuiz />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
