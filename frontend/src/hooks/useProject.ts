import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ProjectCreate } from '../api/client'
import { useAppStore } from '../store/appStore'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: api.projects.list,
    staleTime: 10_000,
  })
}

export function useProject(id: string | null) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => api.projects.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      // Poll every 2s while indexing is in progress
      if (status && !['ready', 'error'].includes(status)) return 2000
      return false
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  const setActiveProject = useAppStore((s) => s.setActiveProject)

  return useMutation({
    mutationFn: (data: ProjectCreate) => api.projects.create(data),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setActiveProject(project)
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  const setActiveProject = useAppStore((s) => s.setActiveProject)

  return useMutation({
    mutationFn: (id: string) => api.projects.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setActiveProject(null)
    },
  })
}

export function useFileTree(projectId: string | null) {
  return useQuery({
    queryKey: ['tree', projectId],
    queryFn: () => api.projects.tree(projectId!),
    enabled: !!projectId,
    staleTime: Infinity, // tree doesn't change after indexing
  })
}

export function useEmbeddings(projectId: string | null, ready: boolean) {
  return useQuery({
    queryKey: ['embeddings', projectId],
    queryFn: () => api.projects.embeddings(projectId!),
    enabled: !!projectId && ready,
    staleTime: Infinity,
  })
}